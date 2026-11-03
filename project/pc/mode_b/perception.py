"""Six detections and three shape-aware neural surfaces, with no motion path."""
import time
import cv2
import numpy as np
from pc.mode_b.profile import CLASSES,TASKS
from pc.mode_b.geometry import pixel_surface,metric_surface,associate_neural_mask
from pc.multiobject.yolo import image_digest,iou


class Perception:
    def __init__(self,detector,surface,profile,confidence=.4,surface_confidence=.7):
        if detector.spec['role']!='mode_b_detector' or detector.spec['classes']!=CLASSES:
            raise ValueError('Use an explicitly packaged six-class mode B detector')
        self.detector,self.surface,self.profile=detector,surface,profile
        self.confidence,self.surface_confidence=confidence,surface_confidence

    def infer(self,frame,frame_index=0,offline=True,geometry=None,metric_pose_verified=False):
        start=time.perf_counter_ns();frame_sha=image_digest(frame)
        detections,meta=self.detector.run(frame,confidence=self.confidence)
        recognition=[]
        for det in detections:
            recognition.append({**det,**self.profile.classify(det['class_name'],det['trained']),
                                'frame_sha256':frame_sha,'frame_index':frame_index})
        results=[];runs=[]
        supported=set(self.surface.spec.get('trained_surface_classes',[]))
        for task,name in TASKS.items():
            matches=[d for d in recognition if d['class_name']==name and d['grasp_target']]
            row={'task_id':task,'class_name':name,'instances':len(matches),'status':'NOT_FOUND',
                 'pixel_surface':None,'metric_surface':None,'physical_execution':False}
            if len(matches)>1:row['status']='MULTIPLE_INSTANCES'
            elif matches:
                d=matches[0];box=np.array(d['bbox_xyxy_raw'],float)
                if any(other is not d and iou(other['bbox_xyxy_raw'],box)>.35 for other in recognition):
                    row['status']='OVERLAP_OR_CLASS_AMBIGUITY'
                elif name not in supported:row['status']='SURFACE_CLASS_NOT_TRAINED'
                else:
                    pad=max(box[2:]-box[:2])*.18
                    crop=[max(0,box[0]-pad),max(0,box[1]-pad),min(frame.shape[1],box[2]+pad),min(frame.shape[0],box[3]+pad)]
                    probs,offset,smeta=self.surface.run(frame,crop)
                    mask=np.where(probs>=self.surface_confidence,255,0).astype(np.uint8)
                    rule=self.profile.task(task)
                    mask,association=associate_neural_mask(mask,offset,box,shape=rule['shape'])
                    runs.append({'task_id':task,**smeta,'mask_association':association})
                    fit=pixel_surface(mask,offset,box,rule['shape'])
                    row['pixel_surface']=fit
                    row['status']='PIXEL_SURFACE_ONLY' if fit else 'NEURAL_SURFACE_GEOMETRY_REJECTED'
                    if geometry is not None:
                        if not metric_pose_verified:row['metric_status']='CALIBRATED_CAMERA_POSE_NOT_VERIFIED'
                        else:
                            try:metric_rule=self.profile.metric_rule(name)
                            except ValueError:row['metric_status']='MEASURED_DIMENSIONS_PENDING'
                            else:
                                row['metric_surface']=metric_surface(mask,offset,box,metric_rule,geometry)
                                row['metric_status']='CANDIDATE_REQUIRES_INDEPENDENT_VALIDATION' if row['metric_surface'] else 'METRIC_GEOMETRY_REJECTED'
                    row['bbox_xyxy_raw']=box.tolist()
            results.append(row)
        return {'schema':'gesture.ai_pc.mode_b_observation.v1','profile_id':self.profile.record['profile_id'],
                'profile_sha256':self.profile.sha256,'frame_sha256':frame_sha,'frame_index':frame_index,
                'offline_snapshot':offline,'recognitions':recognition,'localizations':results,
                'backend':meta['backend'],'surface_backend':self.surface.info,'surface_runs':runs,
                'image_processing':'RAW','physical_execution':False,'path_submissions':0,
                'total_ms':(time.perf_counter_ns()-start)/1e6,
                'metric_localization_accepted':False,'npu_acceptance':'NOT_ACCEPTED','rocm_acceptance':'NOT_ACCEPTED'}


def draw(frame,obs):
    out=frame.copy()
    for det in obs['recognitions']:
        x,y,x2,y2=np.rint(det['bbox_xyxy_raw']).astype(int)
        color=(40,220,80) if det['grasp_target'] else (220,180,80)
        cv2.rectangle(out,(x,y),(x2,y2),color,2)
        label=det['class_name']+f' {det["confidence"]:.2f}'
        if det['task_id']:label+=f' task{det["task_id"]}'
        cv2.putText(out,label,(x,max(25,y-8)),cv2.FONT_HERSHEY_SIMPLEX,.65,color,2)
    for result in obs['localizations']:
        fit=result.get('pixel_surface')
        if not fit:continue
        if fit.get('quad_pixel_uv'):
            cv2.polylines(out,[np.rint(fit['quad_pixel_uv']).astype(np.int32)],True,(255,255,255),2)
            u,v=np.rint(fit['pixel_uv']).astype(int);cv2.drawMarker(out,(u,v),(255,255,255),cv2.MARKER_CROSS,20,2)
        elif fit.get('contour_pixel_uv'):
            cv2.polylines(out,[np.rint(fit['contour_pixel_uv']).astype(np.int32)],True,(255,255,255),2)
    cv2.putText(out,'MODE B / PUBLIC DATA CANDIDATE / PIXELS ONLY / NO MOTION',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,180,255),2)
    return out
