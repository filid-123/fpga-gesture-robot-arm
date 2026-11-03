"""AB workspace adapters; frozen detector/surface packages remain unchanged."""
import numpy as np
from pc.mode_ab.workspace import policy

def workspace_polygon_pixels(geometry):
    """Project the physical table-plane XY marking using the same calibration."""
    import cv2
    x0,x1,y0,y1=policy()['workspace_xy_mm']
    corners=np.array([[x0,y0,0.],[x1,y0,0.],[x1,y1,0.],[x0,y1,0.]],dtype=float)
    image,_=cv2.projectPoints(corners,cv2.Rodrigues(geometry.R)[0],geometry.t,geometry.K,geometry.dist)
    points=image.reshape(4,2)
    if not np.isfinite(points).all():raise ValueError('Workspace marking projection is nonfinite')
    return points


class WorkspaceDetector:
    """Ignore distant desk distractors before same-class instance counting.

    Bounding boxes can include object sides, so retain a half-diagonal of slack.
    The neural top's actual centre is checked without that slack downstream.
    Projection failures remain candidates; they cannot silently disambiguate.
    """
    def __init__(self, detector, geometry, dimensions):
        self.detector, self.geometry, self.dimensions = detector, geometry, dimensions
        self.spec = detector.spec
        self.last_excluded = []

    def run(self, frame, **kwargs):
        detections, meta = self.detector.run(frame, **kwargs)
        x0,x1,y0,y1 = policy()['workspace_xy_mm']; kept=[]; excluded=[]
        for d in detections:
            name=d['class_name']
            if name not in self.dimensions:
                kept.append(d); continue
            size=np.array(self.dimensions[name]['size_mm'],float)
            box=np.array(d['bbox_xyxy_raw'],float)
            try:
                xy=np.asarray(self.geometry.project((box[:2]+box[2:])/2,plane_z_mm=float(size[2])))[:2]
                slack=float(np.linalg.norm(size[:2])/2)
                inside=bool(np.isfinite(xy).all() and x0-slack<=xy[0]<=x1+slack and y0-slack<=xy[1]<=y1+slack)
            except (ValueError,ArithmeticError):
                kept.append(d); continue
            if inside: kept.append(d)
            else: excluded.append(dict(class_name=name,bbox_xyxy_raw=box.tolist(),projected_bbox_centre_xy_mm=xy.tolist()))
        self.last_excluded=excluded
        return kept, {**meta,'workspace_excluded_detections':excluded}


def project_rows(observation, geometry, dimensions, bounds, project):
    """Keep original shape thresholds, admit centres throughout the rectangle.

    A physical object's outline may extend past the pickup-window marking.
    The marking constrains the centre; it is not a collision obstacle.
    """
    from replay_mode_b_visual_bundle import project_rows as frozen_project_rows
    # Evaluate shape independently of the former all-vertices-inside gate.
    rows=frozen_project_rows(observation,geometry,dimensions,
        np.array([-np.inf,-np.inf,np.inf,np.inf]),project)
    x0,x1,y0,y1=policy()['workspace_xy_mm']
    for row in rows:
        top=row.get('top') or {}; centre=top.get('centre_desktop_xyz_mm')
        row['workspace_xy_mm']=[x0,x1,y0,y1]
        row['workspace_semantics']='OBJECT_CENTRE_IN_RECTANGLE'
        row['rejection_reasons']=[]
        if centre is not None:
            xy=np.asarray(centre,float)[:2]
            row['measured_centre_desktop_xy_mm']=xy.tolist()
            inside=bool(np.isfinite(xy).all() and x0<=xy[0]<=x1 and y0<=xy[1]<=y1)
            shape=bool(row.get('geometry_gate_pass'))
            if not shape:row['rejection_reasons'].append('SHAPE_OR_DIMENSIONS')
            if not inside:row['rejection_reasons'].append('CENTRE_OUTSIDE_WORKSPACE')
            row['geometry_gate_pass']=shape and inside
            if not inside:
                row['status']='CENTRE_OUTSIDE_WORKSPACE'
                row['object_centre_desktop_xyz_mm']=None
            elif not shape:row['status']='SHAPE_OR_DIMENSIONS_REJECTED'
        elif not row.get('geometry_gate_pass'):
            row['rejection_reasons'].append(row['status'])
    return rows
