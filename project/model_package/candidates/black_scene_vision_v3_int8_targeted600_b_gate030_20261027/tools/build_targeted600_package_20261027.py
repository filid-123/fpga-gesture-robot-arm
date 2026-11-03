"""Self-contained v3 candidate with new G1/G2 ROM and 26 TRAIN oracle goldens."""
from __future__ import annotations
import hashlib,json,platform,shutil,sys
import numpy as np
import torch
import cv2
import targeted600_release_common_20261027 as c
from build_lab_mix_v2_package_20261024 import save_mem,bank_pack


def refresh(status):
    manifest=c.read(c.OUT/'manifest.json');manifest['status']=status
    manifest['files_sha256']={path.relative_to(c.OUT).as_posix():c.sha(path) for path in sorted(c.OUT.rglob('*'))
        if path.is_file() and path.relative_to(c.OUT).as_posix() not in ('manifest.json','CHECKSUMS.sha256')}
    c.write(c.OUT/'manifest.json',manifest)
    (c.OUT/'CHECKSUMS.sha256').write_text(''.join(f'{c.sha(path)}  {path.relative_to(c.OUT).as_posix()}\n'
        for path in sorted(c.OUT.rglob('*')) if path.is_file() and path.name!='CHECKSUMS.sha256'),encoding='utf-8')


def main():
    if c.OUT.exists():raise FileExistsError('Preserve candidate; no overwrite')
    validation=c.read(c.PARAM/'validation.json')
    if validation['observed_overflow_count']!=0:raise ValueError('Unvalidated numeric overflow')
    torch.set_num_threads(4)
    c.OUT.mkdir()
    for name in ('models','reference/models','golden_integer','hardware_contract','docs','evidence','tools'):(c.OUT/name).mkdir(parents=True)
    shutil.copytree(c.PARAM,c.OUT/'quantized')
    shutil.copy2(c.LOCATOR,c.OUT/'models/locator_best.pt');shutil.copy2(c.CLASSIFIER,c.OUT/'models/classifier_final.pt')
    for name,source in (('locator_model.py',c.LOC/'locator_model.py'),('locator_context_b.py',c.LOC/'locator_context_b.py'),
                        ('gesture_model_v4_six_class.py',c.CLS/'gesture_model_v4_six_class.py')):shutil.copy2(source,c.OUT/'reference/models'/name)
    for name in ('integer_vision_reference.py','preprocessing.py','locator_temporal_pc.py'):
        shutil.copy2(c.BASE/'reference'/name,c.OUT/'reference'/name)
    shutil.copy2(c.TOOLS/'pc_reference_targeted600_template.py',c.OUT/'reference/pc_reference.py')
    verifier=(c.TOOLS/'verify_v2_delivery_template.py').read_text(encoding='utf-8')
    marker="    small = np.zeros((128, 128), np.uint8); small[16:112] = np.arange(128, dtype=np.uint8)[None]"
    extra="""    locator_blob=(ROOT/'quantized/locator/model_rom_16k.bin').read_bytes()
    locator_layout=read(ROOT/'quantized/locator/layout.json')
    assert len(locator_blob)==16384
    for item in locator_layout['layers']:
        name=item['layer'];wo=item['weight_offset'];bo=item['bias_offset']
        assert locator_blob[wo:wo+item['weight_bytes']]==lp[name+'_weight_q'].tobytes()
        assert locator_blob[bo:bo+item['bias_bytes']]==lp[name+'_bias_q'].astype('<i4').tobytes()
    for i,name in enumerate(('conv1','conv2','conv3','conv4','g1')):
        assert np.frombuffer(locator_blob[0x2400+8*i:0x2408+8*i],dtype='<u4').tolist()==[int(lp[name+'_M']),int(lp[name+'_shift'])]
    for i in range(4):
        assert np.frombuffer(locator_blob[0x2440+8*i:0x2448+8*i],dtype='<u4').tolist()==[int(lp['residual_M'][i]),int(lp['residual_shift'][i])]
    frozen=read(ROOT/'hardware_contract/frozen_core_identity.json')
    for name,digest in frozen['core_array_sha256'].items():
        assert hashlib.sha256(lp[name].tobytes()).hexdigest()==digest,name
"""
    if marker not in verifier:raise ValueError('Verifier template changed')
    (c.OUT/'reference/verify_delivery.py').write_text(verifier.replace(marker,extra+marker),encoding='utf-8')
    shutil.copy2(c.BASE/'golden_integer/temporal_examples.json',c.OUT/'golden_integer/temporal_examples.json')
    shutil.copy2(c.BASE/'hardware_contract/integer_contract_rules.py',c.OUT/'hardware_contract/integer_contract_rules.py')
    old_lp=dict(np.load(c.BASE/'quantized/locator/parameters.npz',allow_pickle=False))
    c.write(c.OUT/'hardware_contract/frozen_core_identity.json',{'source_v2_manifest_sha256':c.sha(c.BASE/'manifest.json'),
        'source_v2_Locator_parameters_sha256':c.sha(c.BASE/'quantized/locator/parameters.npz'),
        'core_array_sha256':{key:hashlib.sha256(value.tobytes()).hexdigest() for key,value in old_lp.items() if not key.startswith(('g1_','g2_','residual_'))}})
    c.write(c.OUT/'hardware_contract/runtime_gate.json',{'probability':.3,'raw_signed_int32':-11748,'comparison':'>=',
        'raw_confidence_scale':float(old_lp['conv5_output_scale'][0]),'reject_boundary':-11749,'accept_boundary':-11748,
        'in_Locator_weight_ROM':False,'changed_from_v2':False})
    c.write(c.OUT/'hardware_contract/class_mapping.json',{'class_order':list(c.CLASS_NAMES),'background_id':0,
        'no_detection_or_background_produces_target_action':False,'argmax_tie':'first strict greater','legacy_capture_numeric_ids_not_action_codes':True})
    sys.path.insert(0,str(c.OUT/'reference'));sys.path.insert(0,str(c.OUT/'reference/models'))
    ops=c.module('target600_package_ops',c.OUT/'reference/integer_vision_reference.py')
    pc=c.module('target600_package_pc',c.OUT/'reference/pc_reference.py')
    runtime=ops.IntegerVision(c.OUT);approved=pc.VisionReference()
    records=c.rows(c.GEODATA/'train_manifest.jsonl')+[r for r in c.rows(c.DATA/'train_manifest.jsonl') if r['cohort']=='targeted_TRAIN']
    eligible={r['image_sha256'] for r in c.rows(c.DATA/'train_manifest.jsonl') if r['eligible']}
    selected=[]
    for cohort in ('original_TRAIN','lab_TRAIN','usb_midfar_TRAIN','targeted_TRAIN'):
        for label in c.CLASS_NAMES:
            selected.append(next(row for row in records if row['cohort']==cohort and row['class_name']==label and row['image_sha256'] in eligible))
    rejected=next(row for row in records if row['cohort']=='targeted_TRAIN' and row['class_name']=='one' and not row['eligible'])
    tilted=next(row for row in records if row['cohort']=='targeted_TRAIN' and row['class_name']=='two'
                and row['requested_condition_prompt_only']['orientation']=='LEAN_LEFT' and row['image_sha256'] not in {r['image_sha256'] for r in selected})
    selected.extend((rejected,tilted));assert len(selected)==len({row['image_sha256'] for row in selected})==26
    index={'kind':'v3_targeted600_full_INT8_CNN_TRAIN_goldens','selection':'one_per_class_per_four_TRAIN_cohorts_plus_rejected_one_and_leftlean_two',
           'all_source_role':'TRAIN','samples':[]};ranges={}
    for number,row in enumerate(selected):
        name=f'sample_{number:02d}';folder=c.OUT/'golden_integer'/name;folder.mkdir();(folder/'banks').mkdir()
        if c.sha(row['image'])!=row['image_sha256']:raise ValueError('Golden TRAIN image changed')
        shutil.copy2(row['image'],folder/'source.png');frame=c.PRE.read_bgr_image(folder/'source.png');small=c.PRE.preprocess_bgr_to_locator_input(frame)
        output,ls,observed=ops.forward_locator(small,runtime.locator);c.merge_ranges(ranges,observed);decoded=ops.decode_locator(output,runtime.locator)
        roi=c.roi_for(decoded);crop=c.PRE.classifier_from_small(small,roi);logits,cs,_=ops.forward_classifier(crop,runtime.classifier)
        _,lo,_=ops.forward_locator(small,runtime.locator,oracle=True);_,co,_=ops.forward_classifier(crop,runtime.classifier,oracle=True)
        if not all(np.array_equal(value,lo[key]) for key,value in ls.items()) or not all(np.array_equal(value,co[key]) for key,value in cs.items()):raise ValueError('Independent tap/scalar oracle differs')
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);x0,y0,x1,y1=roi;ss=(x1-x0+4)//5
        scalar=np.array([[gray[5*(y0//5+y*ss//32),5*(x0//5+x*ss//32)] for x in range(32)] for y in range(32)],np.uint8)
        if not np.array_equal(crop,scalar):raise ValueError('Scalar VGA B oracle differs')
        combined={'locator_input_u8':small,'classifier_input_u8':crop,**{'locator_'+k:v for k,v in ls.items()},**{'classifier_'+k:v for k,v in cs.items()}}
        np.savez_compressed(folder/'layers.npz',**combined);np.save(folder/'locator_input_u8.npy',small,allow_pickle=False);np.save(folder/'classifier_input_u8.npy',crop,allow_pickle=False)
        specs={key:save_mem(folder/(key+'.mem'),value) for key,value in combined.items()}
        _,floats=approved.forward_classifier(crop);np.savez_compressed(folder/'float_classifier_layers.npz',**floats)
        stream=[((channel*256+cell)<<32)|(int(output[channel,cell//16,cell%16])&0xFFFFFFFF) for cell in range(256) for channel in range(5)]
        (folder/'locator_output_stream_addr12_data32.mem').write_text(''.join(f'{value:011X}\n' for value in stream),encoding='ascii')
        act0=bank_pack(ls['conv3_pool_u8']);residual=ls['g2_acc_i32'].astype(np.int64).reshape(4,256)&0xFFFFFFFF
        for channel in range(4):
            for byte in range(4):act0[2*channel+(byte>>1),0x200+(byte&1)*256:0x300+(byte&1)*256]=(residual[channel]>>(8*byte))&255
        for kind,values in (('act0_F3_and_residual',act0),('act1_G1',bank_pack(ls['g1_u8'])),('act1_F4',bank_pack(ls['conv4_u8']))):
            for k in range(8):(folder/'banks'/f'{kind}_bank{k}.bin').write_bytes(values[k].tobytes());save_mem(folder/'banks'/f'{kind}_bank{k}.mem',values[k])
        c.write(folder/'layout.json',{'arrays':specs,'output_stream':'44bit{addr12,data32};cell-major/channel0..4',
            'bank_valid_bytes':{'act0_F3_and_residual':[0,1024],'act1_G1':[0,256],'act1_F4':[0,768]},'zero_unwritten_bytes':'fixture padding only, not whole RAM clear requirement'})
        index['samples'].append({'id':name,'image':f'golden_integer/{name}/source.png','source_role':'TRAIN','source_image_id':row['image_id'],
            'source_sha256':row['image_sha256'],'class_label':row['class_name'],'vectors':f'golden_integer/{name}/layers.npz',
            'float_classifier_vectors':f'golden_integer/{name}/float_classifier_layers.npz',
            'classifier_input_role':'production' if decoded['detected'] else 'rejected_peak_diagnostic_not_live_action',
            'pipeline':runtime.predict(frame),'pipeline_approved_PC':approved.predict(frame)})
        print({'golden':name,'label':row['class_name'],'detected':decoded['detected'],'oracle':'EXACT'},flush=True)
    c.write(c.OUT/'golden_integer/index.json',index)
    c.write(c.OUT/'evidence/golden_build_validation.json',{'status':'PASS_V3_26_FULL_LAYER_TRAIN_GOLDENS','samples':26,
        'independent_tap_scalar_Dense_oracle_samples':26,'B_VGA_scalar_exact':True,'ranges':ranges,'RTL_simulated':False})
    for source,name in ((c.PARAM/'validation.json','quantization_validation.json'),(c.PARAM/'validation_rows.json','quantization_validation_rows.json'),
                        (c.CLS/'reports/classifier_usb_targeted_resume60_600_analysis_20261026/RESULTS_CN.md','training_results_CN.md')):
        shutil.copy2(source,c.OUT/'evidence'/name)
    for source in (c.TOOLS/'targeted600_release_common_20261027.py',c.TOOLS/'export_targeted600_int8_20261027.py',
                   c.TOOLS/'build_targeted600_package_20261027.py',c.TOOLS/'pc_reference_targeted600_template.py',
                   c.TOOLS/'export_black_scene_integer.py',c.TOOLS/'export_lab_mix_v2_20261024.py',c.TOOLS/'build_lab_mix_v2_package_20261024.py',c.TOOLS/'verify_v2_delivery_template.py'):
        shutil.copy2(source,c.OUT/'tools'/source.name)
    c.write(c.OUT/'dependency_versions.json',{'python':platform.python_version(),'numpy':np.__version__,'opencv':cv2.__version__,
        'torch':str(torch.__version__),'integer_reference_requires':['numpy','opencv-python'],'approved_PC_reference_requires':['torch'],'CUDA_required':False})
    (c.OUT/'requirements.txt').write_text('numpy>=1.24\nopencv-python>=4.8\n# Approved PC floating reference additionally requires torch>=2.1 (CPU supported).\n',encoding='utf-8')
    (c.OUT/'.gitignore').write_text('__pycache__/\n*.pyc\n!quantized/**/*.bin\n!golden_integer/**/*.bin\n',encoding='utf-8')
    (c.OUT/'.gitattributes').write_text('* -text -filter\n',encoding='utf-8')
    c.write(c.OUT/'manifest.json',{'release_id':c.ID,'date':'2026-10-27','status':'BUILT_PENDING_DOCS_AND_PORTABLE_VERIFICATION',
        'locator':{'path':'models/locator_best.pt','sha256':c.LOC_SHA,'parameters':8717,'G1_G2_changed_from_v2':True,'integer_core_unchanged':True},
        'classifier':{'path':'models/classifier_final.pt','sha256':c.CLS_SHA,'parameters':39110,'class_names':list(c.CLASS_NAMES),'targeted_stage_updates':600},
        'pc_contract':{'threshold':.3,'threshold_raw_int32':-11748,'roi_margin':.18,'preprocessing':'Phase2_B_exact_small_ROI_nearest32','stabilization_enabled':True},
        'git':{'repository':'https://github.com/filid-123/Gesture.git','branch':'dev/Rain','candidate_path':'model_package/candidates/'+c.ID},
        'TEST_read':False,'new_training':False,'RTL_simulated':False,'board_tested':False,'files_sha256':{}})
    refresh('GOLDENS_BUILT_PENDING_DOCS_AND_PORTABLE_VERIFICATION')
    print({'stage':'PACKAGE_GOLDENS_BUILT','files':sum(path.is_file() for path in c.OUT.rglob('*')),'output':str(c.OUT)},flush=True)


if __name__=='__main__':main()
