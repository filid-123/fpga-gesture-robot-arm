"""TRAIN-only strict max PTQ: preserve integer core, new G1/G2 and targeted600 CLF."""
from __future__ import annotations
import argparse,hashlib
from collections import Counter
import numpy as np
import torch
import targeted600_release_common_20261027 as c


def export():
    if c.PARAM.exists():raise FileExistsError('Preserve frozen quantization; no overwrite')
    torch.set_num_threads(4);locator,classifier=c.models();records,small,eligible,sources=c.train_sources()
    lp=dict(np.load(c.BASE/'quantized/locator/parameters.npz',allow_pickle=False));original={key:value.copy() for key,value in lp.items()}
    if int(lp['confidence_threshold_i32'])!=-11748:raise ValueError('Wrong integer gate')
    f3=[];base=[];ranges={}
    for i,image in enumerate(small):
        output,stages,observed=c.OPS.forward_locator(image,lp);decoded=c.OPS.decode_locator(output,lp)
        expected=records[i].get('integer_raw_confidence',records[i].get('confidence_raw_i32'))
        if decoded['confidence_raw_i32']!=expected:raise ValueError('TRAIN confidence no longer matches frozen records')
        f3.append(stages['conv3_pool_u8']);base.append(stages['conv5_acc_i32'])
        c.merge_ranges(ranges,{key:value for key,value in observed.items() if key.startswith('conv')})
        if (i+1)%100==0:print({'stage':'FROZEN_INTEGER_TRAIN_FEATURES','done':i+1,'total':len(records)},flush=True)
    f3=np.stack(f3);base=np.stack(base);maximum=0.
    with torch.inference_mode():
        for start in range(0,len(f3),64):
            x=torch.from_numpy(f3[start:start+64].astype(np.float32)*float(lp['conv3_output_scale']))
            maximum=max(maximum,float(locator.geometry_relu(locator.geometry_g1(x)).max()))
    quant=c.QUANT['quant_layer'];gscale=max(maximum/255,1e-12)
    p,gi1=quant(locator.geometry_g1.weight,locator.geometry_g1.bias,float(lp['conv3_output_scale']),gscale)
    lp.update({'g1_'+key:value for key,value in p.items()})
    p,gi2=quant(locator.geometry_g2.weight,locator.geometry_g2.bias,gscale,per_channel=True)
    lp.update({'g2_'+key:value for key,value in p.items()})
    pairs=[c.QUANT['multiplier'](float(p['bias_scale'][i]/lp['conv5_output_scale'][i+1])) for i in range(4)]
    lp['residual_M']=np.array([pair[0] for pair in pairs],np.int32);lp['residual_shift']=np.array([pair[1] for pair in pairs],np.uint32)
    if not c.same_core(lp,original):raise ValueError('Frozen core quantization changed')
    desired={row['image_sha256'] for row in eligible};crop_by_hash={};boxes=[];rois=[]
    for i,image in enumerate(small):
        output,observed=c.from_base(f3[i],base[i],lp);c.merge_ranges(ranges,observed);decoded=c.OPS.decode_locator(output,lp)
        roi=c.roi_for(decoded);boxes.append(decoded['bbox_source']);rois.append(roi)
        if records[i]['image_sha256'] in desired:crop_by_hash[records[i]['image_sha256']]=c.PRE.classifier_from_small(image,roi)[None]
    bank=np.stack([crop_by_hash[row['image_sha256']] for row in eligible])
    if len(bank)!=959:raise ValueError('Classifier calibration must retain959 approved parents')
    _,maxima=c.HELPER.float_forward(classifier,bank);cp={};info={};previous_scale=1/255;state=classifier.state_dict()
    for name in ('conv1','conv2','conv3','fc1','fc2'):
        output_scale=max(maxima[name]/255,1e-12) if name!='fc2' else None
        parameters,layer_info=quant(state[name+'.weight'],state[name+'.bias'],previous_scale,output_scale)
        cp.update({name+'_'+key:value for key,value in parameters.items()});info[name]=layer_info
        if output_scale is not None:previous_scale=output_scale
    cp['fc2_output_scale']=cp['fc2_bias_scale'];c.PARAM.mkdir();c.pack_parameters(lp,cp,{'g1':gi1,'g2':gi2},info)
    for path in (c.BASE/'manifest.json',c.BASE/'quantized/locator/parameters.npz',c.BASE/'reference/integer_vision_reference.py',
                 c.BASE/'reference/preprocessing.py',c.TOOLS/'targeted600_release_common_20261027.py',c.TOOLS/'export_targeted600_int8_20261027.py',
                 c.TOOLS/'export_black_scene_integer.py',c.TOOLS/'export_lab_mix_v2_20261024.py'):sources[str(path)]=c.sha(path)
    calibration={'role':'TRAIN_ONLY_STATIC_PTQ','locator_TRAIN_frames':970,'classifier_TRAIN_crops':959,
        'range_policy':'strict100percent_float_ReLU_maximum;G1_input_is_actual_integer_F3_dequantized;CLF_input_is_new_integer_geometry_B_ROI',
        'G1_activation_maximum':maximum,'classifier_activation_maxima':maxima,
        'locator_by_cohort':dict(Counter(row['cohort'] for row in records)),
        'classifier_by_cohort':dict(Counter(row['cohort'] for row in eligible)),
        'classifier_by_class':dict(Counter(row['class_name'] for row in eligible)),
        'all_prior_classifier_exclusions_preserved':True,'GT_crop':False,'VAL_or_TEST_used_for_calibration':False,
        'locator_parent_ids':[{'image_id':row['image_id'],'source_sha256':row['image_sha256']} for row in records],
        'classifier_crop_hashes':[{'image_id':row['image_id'],'source_sha256':row['image_sha256'],
            'input_sha256':hashlib.sha256(bank[i,0].tobytes()).hexdigest()} for i,row in enumerate(eligible)]}
    c.write(c.PARAM/'calibration.json',calibration)
    c.write(c.REPORT/'quantization_source_bindings.json',sources)
    np.savez_compressed(c.CACHE,small=small,f3=f3,base=base,classifier_inputs=bank,train_boxes=np.array(boxes),train_rois=np.array(rois))
    frozen={path.relative_to(c.PARAM).as_posix():c.sha(path) for path in c.PARAM.rglob('*') if path.is_file()}
    c.write(c.PARAM/'manifest.json',{'status':'PARAMETERS_FROZEN_BEFORE_DEVELOPMENT_VALIDATION','release_id':c.ID,
        'locator_model_sha256':c.LOC_SHA,'classifier_model_sha256':c.CLS_SHA,'integer_base_and_confidence_parameters_unchanged':True,
        'confidence_threshold_raw_i32':-11748,'threshold_probability':.3,'new_geometry_layers':{'g1':gi1,'g2':gi2},
        'residual_M':lp['residual_M'].tolist(),'residual_shift':lp['residual_shift'].tolist(),'classifier_layers':info,
        'base_ROM_prefix_unchanged':True,'whole_Locator_ROM_changed':c.sha(c.PARAM/'locator/model_rom_16k.bin')!=c.sha(c.BASE/'quantized/locator/model_rom_16k.bin'),
        'files_sha256':frozen,'TEST_read':False,'new_training':False,'RTL_simulated':False})
    c.write(c.REPORT/'TRAIN_locator_ranges.json',ranges)
    print({'stage':'PTQ_FROZEN_BEFORE_DEV','locator_TRAIN':970,'classifier_TRAIN':959,'base_unchanged':True,'G1_max':maximum,'classifier_maxima':maxima},flush=True)


def validate():
    manifest=c.read(c.PARAM/'manifest.json')
    if (c.PARAM/'validation.json').exists():raise FileExistsError('Preserve completed quantization validation')
    for path,digest in manifest['files_sha256'].items():
        if c.sha(c.PARAM/path)!=digest:raise ValueError('Frozen quantization changed')
    for path,digest in c.read(c.REPORT/'quantization_source_bindings.json').items():
        if c.sha(path)!=digest:raise ValueError('Calibration source changed')
    torch.set_num_threads(4);locator,classifier=c.models()
    lp=dict(np.load(c.PARAM/'locator/parameters.npz',allow_pickle=False));cp=dict(np.load(c.PARAM/'classifier/parameters.npz',allow_pickle=False))
    ranges=c.read(c.REPORT/'TRAIN_locator_ranges.json');metrics={};details={}
    with np.load(c.CACHE,allow_pickle=False) as cache:train_crops=cache['classifier_inputs'].copy()
    classifier_ranges={}
    for i,crop in enumerate(train_crops):
        _,_,observed=c.OPS.forward_classifier(crop[0],cp);c.merge_ranges(classifier_ranges,observed)
    # DEV files are first consumed after all new integer parameters were frozen.
    baseline=c.read(c.CLASSIFIER.parent/'final_validation.json');baseline_logits=dict(np.load(c.CLASSIFIER.parent/'final_validation_logits.npz',allow_pickle=False))
    for role in ('old_dev','usb_dev','targeted_dev'):
        records=c.rows(c.DATA/(role+'_manifest.jsonl'));approved_inputs=np.load(c.DATA/(role+'_inputs_u8.npy'),allow_pickle=False)
        pred_same=[];pred_full=[];new_crops=[];gates=[];decoded_rows=[]
        for i,row in enumerate(records):
            frame=c.PRE.read_bgr_image(row['image'])
            if c.sha(row['image'])!=row['image_sha256']:raise ValueError('DEV raw changed')
            small=c.PRE.preprocess_bgr_to_locator_input(frame);output,_,observed=c.OPS.forward_locator(small,lp);c.merge_ranges(ranges,observed)
            decoded=c.OPS.decode_locator(output,lp)
            expected=row.get('integer_raw_confidence',row.get('confidence_raw_i32'))
            if decoded['confidence_raw_i32']!=expected or decoded['detected']!=row['gate_passed']:raise ValueError('Frozen confidence changed on DEV')
            crop=c.PRE.classifier_from_small(small,c.roi_for(decoded));new_crops.append(crop[None]);gates.append(decoded['detected']);decoded_rows.append(decoded)
            same,_,_=c.OPS.forward_classifier(approved_inputs[i,0],cp);pred_same.append(int(same.argmax()))
            full,_,observed=c.OPS.forward_classifier(crop,cp);pred_full.append(int(full.argmax()));c.merge_ranges(classifier_ranges,observed)
        floating,_=c.HELPER.float_forward(classifier,np.stack(new_crops));new_float=floating.argmax(1);original=baseline_logits[role].argmax(1)
        modes={'approved_PC_baseline':c.summarize(records,original,[row['gate_passed'] for row in records]),
               'approved_PC_ROI_integer_classifier':c.summarize(records,pred_same,gates),
               'new_integer_ROI_float_classifier':c.summarize(records,new_float,gates),
               'full_integer':c.summarize(records,pred_full,gates)}
        if modes['approved_PC_baseline']['correct_hand']!=baseline['datasets'][role]['correct_hand']:raise ValueError('PC baseline mismatch')
        metrics[role]=modes
        details[role]=[{'image_id':row['image_id'],'truth':row['class_name'],'GT_source':row['GT_source'],'detected':bool(gates[i]),
            'PC_ROI':row['roi_source'],'integer_ROI':list(c.roi_for(decoded_rows[i])),'integer_bbox':decoded_rows[i]['bbox_source'],
            'approved_PC_class':c.CLASS_NAMES[int(original[i])],'same_ROI_integer_class':c.CLASS_NAMES[pred_same[i]],
            'integer_ROI_float_class':c.CLASS_NAMES[int(new_float[i])],'full_integer_class':c.CLASS_NAMES[pred_full[i]]} for i,row in enumerate(records)]
        print({'stage':'DEV_COMPARISON','role':role,'correct':{name:item['correct_hand'] for name,item in modes.items()}},flush=True)
    overflow=sum(item['overflow_count'] for item in ranges.values())+sum(item['overflow_count'] for item in classifier_ranges.values())
    if overflow:raise OverflowError('Observed signed32 overflow; do not publish as validated')
    for path,digest in manifest['files_sha256'].items():
        if c.sha(c.PARAM/path)!=digest:raise ValueError('Parameters changed after DEV')
    c.write(c.PARAM/'validation.json',{'status':'VALIDATED_NEW_GEOMETRY_AND_CLASSIFIER_PTQ_FROZEN_BEFORE_DEV',
        'metrics':metrics,'locator_ranges_TRAIN_and_DEV':ranges,'classifier_ranges_TRAIN_and_DEV':classifier_ranges,
        'observed_overflow_count':overflow,'confidence_gate_unchanged':True,'VAL_used_to_select_quantization':False,'TEST_read':False,
        'new_training':False,'RTL_simulated':False,'board_tested':False})
    c.write(c.PARAM/'validation_rows.json',details)
    print({'stage':'PTQ_VALIDATION_COMPLETE','overflow':overflow},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--validate',action='store_true');args=parser.parse_args()
    validate() if args.validate else export()
