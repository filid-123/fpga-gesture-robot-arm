"""Shared, TRAIN-only-calibration helpers for the targeted600 INT8 candidate."""
from __future__ import annotations
import hashlib,importlib.util,json,math,sys
from pathlib import Path
import cv2 as cv
import numpy as np
import torch

ROOT=Path(__file__).resolve().parent.parent;TOOLS=ROOT/'handoff_tools'
BASE=ROOT/'handoff/black_scene_vision_v2_int8_B_gate030_20261024'
ID='black_scene_vision_v3_int8_targeted600_B_gate030_20261027'
PARAM=ROOT/'quantized_black_scene_v3_targeted600_20261027';OUT=ROOT/'handoff'/ID
REPORT=ROOT/'reports/targeted600_git_preparation_20261027';CACHE=REPORT/'quantization_work_cache.npz'
CLS=ROOT/'gesture_CNN';LOC=ROOT/'hand_locator'
DATA=CLS/'datasets/classifier_usb_targeted_20261026';GEODATA=LOC/'datasets/locator_usb_midfar_geometry_20261026'
LOCATOR=LOC/'models_locator_usb_midfar_old_resume400_20261026/locator_final.pt'
CLASSIFIER=CLS/'models_classifier_usb_targeted_resume60_600_20261026/classifier_final.pt'
LOC_SHA='a09c85d89469f7fc5ebf57990ac0f2740458a7df2ace8da24dc702709dd8e06d'
CLS_SHA='da50fec1e717b4fb4b94cd2bdca7fceb7fadd8383f0f4b8661b1d8ac4ca4e227'
sys.path.insert(0,str(CLS));sys.path.insert(0,str(LOC))
from gesture_model_v4_six_class import GestureCNN6,CLASS_NAMES
from locator_context_b import HandLocatorNetContextB

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def rows(path):return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
def native(value):
    if isinstance(value,dict):return {key:native(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [native(item) for item in value]
    if isinstance(value,np.generic):return value.item()
    return value
def write(path,value):Path(path).write_text(json.dumps(native(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);sys.modules[name]=result;spec.loader.exec_module(result);return result
OPS=module('target600_int_ops',BASE/'reference/integer_vision_reference.py')
PRE=module('target600_B',BASE/'reference/preprocessing.py')
HELPER=module('target600_quant_helpers',TOOLS/'export_lab_mix_v2_20261024.py')
QUANT=HELPER.helpers()

def models():
    if sha(LOCATOR)!=LOC_SHA or sha(CLASSIFIER)!=CLS_SHA:raise ValueError('Frozen source weights changed')
    payload=torch.load(LOCATOR,map_location='cpu',weights_only=False)
    locator=HandLocatorNetContextB(branch_seed=payload['branch_seed']);locator.load_state_dict(payload['model_state_dict'],strict=True)
    original=torch.load(BASE/'models/locator_best.pt',map_location='cpu',weights_only=False)['model_state_dict']
    if not all(torch.equal(value,original[name]) for name,value in locator.state_dict().items() if name.startswith('base.')):raise ValueError('Locator base is not frozen E3')
    cp=torch.load(CLASSIFIER,map_location='cpu',weights_only=False)
    if tuple(cp['class_names'])!=CLASS_NAMES or cp['optimizer_updates']!=600:raise ValueError('Classifier contract differs')
    classifier=GestureCNN6();classifier.load_state_dict(cp['model_state_dict'],strict=True)
    return locator.eval().requires_grad_(False),classifier.eval().requires_grad_(False)

def train_sources():
    legacy=rows(GEODATA/'train_manifest.jsonl');classifier_rows=rows(DATA/'train_manifest.jsonl')
    targeted=[row for row in classifier_rows if row['cohort']=='targeted_TRAIN'];records=legacy+targeted
    if len(legacy)!=810 or len(targeted)!=160 or len(records)!=970:raise ValueError('Unexpected legal TRAIN pool')
    eligible=[row for row in classifier_rows if row['eligible']]
    if len(eligible)!=959 or len({row['image_sha256'] for row in records})!=970:raise ValueError('TRAIN identity/eligibility differs')
    approved_roots=[LOC/'datasets'/name/'train' for name in ('field_project_scene_20261006','field_black_lab_light_20261023','field_usb_midfar_match_20261026','field_usb_targeted_pose_edge_20261026')]
    annotation_cache={};small=[];bindings={str(path):sha(path) for path in (GEODATA/'train_manifest.jsonl',DATA/'train_manifest.jsonl',LOCATOR,CLASSIFIER)}
    for row in records:
        image=Path(row['image']).resolve();ap=Path(row['annotation_path']).resolve()
        if row['split']!='train' or not any(image.is_relative_to(path.resolve()) for path in approved_roots):raise ValueError('NonTRAIN calibration source')
        if sha(image)!=row['image_sha256']:raise ValueError('TRAIN raw hash changed')
        if ap not in annotation_cache:
            doc=read(ap)
            if not doc['review_complete']:raise ValueError('Unreviewed source labels')
            annotation_cache[ap]={item['image']:item for item in doc['annotations']};bindings[str(ap)]=sha(ap)
        annotation=annotation_cache[ap][image.relative_to(ap.parent).as_posix()]
        if annotation['review_status']!='accepted':raise ValueError('Unaccepted TRAIN source')
        label=annotation['gesture'] if annotation['sample_type']=='hand' else 'background'
        if label!=row['class_name']:raise ValueError('Calibration label identity mismatch')
        frame=PRE.read_bgr_image(image);small.append(PRE.preprocess_bgr_to_locator_input(frame));bindings[str(image)]=row['image_sha256']
    if not {row['image_sha256'] for row in eligible}<={row['image_sha256'] for row in records}:raise ValueError('Classifier calibration parent missing')
    return records,np.stack(small),eligible,bindings

def same_core(new,old):
    return all(np.array_equal(value,old[key]) for key,value in new.items() if not key.startswith(('g1_','g2_','residual_')))

def from_base(f3,base,lp):
    g1,full1=OPS.convolution(f3,lp['g1_weight_q'],lp['g1_bias_q'],2)
    shifted=OPS.round_shift(g1,int(lp['g1_M']),int(lp['g1_shift']));hidden=np.clip(shifted,0,255).astype(np.uint8)
    g2,full2=OPS.convolution(hidden,lp['g2_weight_q'],lp['g2_bias_q'],5)
    aligned=OPS.round_shift(g2,lp['residual_M'][:,None,None],lp['residual_shift'][:,None,None])
    total=base[1:].astype(np.int64)+aligned;out=np.concatenate((base[:1],OPS.wrap32(total)))
    ranges={}
    for name,full in (('g1',full1),('g2',full2),('fusion',total)):
        ranges[name]={'min':int(full.min()),'max':int(full.max()),'overflow_count':int(((full<-(1<<31))|(full>(1<<31)-1)).sum())}
    ranges['g1'].update(high_saturation_count=int((shifted>255).sum()),activation_elements=int(shifted.size))
    return out,ranges

def roi_for(decoded):
    box=decoded['bbox_source']
    if box[2]<=box[0] or box[3]<=box[1]:raise ValueError('Invalid production peak ROI; no GT replacement permitted')
    return PRE.square_roi_from_source_box(PRE.clipped_int_box(box,640,480),640,480,.18)

def merge_ranges(out,current):HELPER.merge_ranges(out,current)

def pack_parameters(lp,cp,locator_info,classifier_info):
    for name,p in (('locator',lp),('classifier',cp)):
        (PARAM/name).mkdir(parents=True);np.savez_compressed(PARAM/name/'parameters.npz',**p)
    layout=read(BASE/'quantized/locator/layout.json');blob=bytearray(16384)
    for row in layout['layers']:
        name=row['layer'];blob[row['weight_offset']:row['weight_offset']+row['weight_bytes']]=lp[name+'_weight_q'].tobytes()
        blob[row['bias_offset']:row['bias_offset']+row['bias_bytes']]=lp[name+'_bias_q'].astype('<i4').tobytes()
    for i,name in enumerate(('conv1','conv2','conv3','conv4','g1')):blob[0x2400+8*i:0x2408+8*i]=np.array([lp[name+'_M'],lp[name+'_shift']],dtype='<u4').tobytes()
    for i in range(4):blob[0x2440+8*i:0x2448+8*i]=np.array([lp['residual_M'][i],lp['residual_shift'][i]],dtype='<u4').tobytes()
    (PARAM/'locator/model_rom_16k.bin').write_bytes(blob);QUANT['write_mem'](PARAM/'locator/model_rom_16k.mem',blob)
    write(PARAM/'locator/layout.json',layout)
    old=(BASE/'quantized/locator/model_rom_16k.bin').read_bytes()
    if bytes(blob[:0x1DC0])!=old[:0x1DC0] or bytes(blob[0x2400:0x2420])!=old[0x2400:0x2420]:raise ValueError('Base ROM changed')
    cblob=bytearray();layers=[]
    for name in ('conv1','conv2','conv3','fc1','fc2'):
        cblob.extend(bytes((-len(cblob))%4));wo=len(cblob);wb=cp[name+'_weight_q'].tobytes();cblob.extend(wb)
        cblob.extend(bytes((-len(cblob))%4));bo=len(cblob);bb=cp[name+'_bias_q'].astype('<i4').tobytes();cblob.extend(bb)
        layers.append({'layer':name,'weight_offset_bytes':wo,'weight_size_bytes':len(wb),'bias_offset_bytes':bo,'bias_size_bytes':len(bb)})
    if len(cblob)!=39488:raise ValueError('Classifier layout changed')
    (PARAM/'classifier/weights_all.bin').write_bytes(cblob);QUANT['write_mem'](PARAM/'classifier/weights_all.mem',cblob)
    descriptors=QUANT['read_legacy_descriptor_helpers']()['build_layer_descriptors']({name:{'M':int(cp[name+'_M']) if name!='fc2' else 0,'shift':int(cp[name+'_shift']) if name!='fc2' else 0} for name in classifier_info},layers)
    if descriptors[7][0]!=0x01060102:raise ValueError('Six-class descriptor changed')
    dblob=np.array(descriptors,dtype='<u4').tobytes();(PARAM/'classifier/layer_descriptors.bin').write_bytes(dblob);QUANT['write_mem'](PARAM/'classifier/layer_descriptors.mem',dblob)
    write(PARAM/'classifier/layout_and_descriptors.json',{'bytes':len(cblob),'layers':layers,'descriptor_words':descriptors,'final_Cout':6})

def summarize(records,predictions,gates):
    matrix=np.zeros((6,7),np.int64)
    for row,pred,gate in zip(records,predictions,gates,strict=True):matrix[row['class_id'],int(pred) if gate else 6]+=1
    return {'hand_total':int(matrix[1:].sum()),'hand_detected':int(matrix[1:,:6].sum()),
            'correct_hand':int(sum(matrix[i,i] for i in range(1,6))),'empty_total':int(matrix[0].sum()),
            'empty_detector_false_positive':int(matrix[0,:6].sum()),'empty_effective_gesture_false_positive':int(matrix[0,1:6].sum()),
            'by_class_correct':{CLASS_NAMES[i]:int(matrix[i,i]) for i in range(1,6)},
            'columns':[*CLASS_NAMES,'no_detection'],'confusion_matrix':matrix.tolist()}
