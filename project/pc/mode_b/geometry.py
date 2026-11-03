"""Shape-specific known-height localization; all results are non-executable."""
import cv2
import numpy as np
from pc.multiobject.pixel_top import fit_pixel_quad


def fit_registered_quad(mask,offset,box):
    """Try contour simplification, then independently fitted straight edges.

    Rounded corners of a long eraser can cause contour simplification to cut
    into its face. A minimum-area rectangle supplies edge membership only;
    the four independently fitted lines may form a projective quadrilateral.
    Every proposal still needs >=0.85 IoU with the original neural mask.
    """
    legacy=fit_pixel_quad(mask,offset,box)
    if legacy is not None:return legacy
    found=contour_mask(mask)
    if found is None:return None
    clean,contour=found
    points=contour.reshape(-1,2).astype(float)
    corners=cv2.boxPoints(cv2.minAreaRect(contour)).astype(float)
    lengths=np.linalg.norm(np.roll(corners,-1,axis=0)-corners,axis=1)
    if min(lengths)<4:return None
    starts=corners;edges=np.roll(corners,-1,axis=0)-corners
    relative=points[:,None,:]-starts[None,:,:]
    distances=np.abs(relative[:,:,0]*edges[None,:,1]-relative[:,:,1]*edges[None,:,0])/lengths
    nearest=distances.argmin(1)
    lines=[]
    for i in range(4):
        projection=(relative[:,i]@edges[i])/(lengths[i]**2)
        selected=points[(nearest==i)&(projection>=.15)&(projection<=.85)
                        &(distances[:,i]<=max(2.,min(lengths)*.12))]
        if len(selected)<6:return None
        span=np.ptp((selected-starts[i])@edges[i])/lengths[i]
        if span<lengths[i]*.35:return None
        vx,vy,x,y=cv2.fitLine(selected.astype(np.float32),cv2.DIST_HUBER,0,.01,.01).reshape(-1)
        normal=np.array([-vy,vx],dtype=float)
        lines.append((normal,float(normal@np.array([x,y]))))
    quad=[]
    for i in range(4):
        n1,b1=lines[(i-1)%4];n2,b2=lines[i]
        matrix=np.stack((n1,n2))
        if abs(np.linalg.det(matrix))<.08:return None
        quad.append(np.linalg.solve(matrix,[b1,b2]))
    quad=np.asarray(quad)
    if (not np.isfinite(quad).all() or np.any(quad<=1)
            or np.any(quad>=np.array([mask.shape[1]-2,mask.shape[0]-2]))
            or not cv2.isContourConvex(np.rint(quad).astype(np.int32))):return None
    fitted=np.zeros_like(clean)
    cv2.fillConvexPoly(fitted,np.rint(quad).astype(np.int32),255)
    agreement=np.count_nonzero((fitted>0)&(clean>0))/max(1,np.count_nonzero((fitted>0)|(clean>0)))
    if agreement<.85:return None
    raw=quad+offset
    homogeneous=np.column_stack((raw,np.ones(4)))
    centre=np.cross(np.cross(homogeneous[0],homogeneous[2]),np.cross(homogeneous[1],homogeneous[3]))
    if abs(centre[2])<1e-8:return None
    centre=centre[:2]/centre[2]
    if np.any(centre<np.asarray(box[:2])) or np.any(centre>np.asarray(box[2:])):return None
    return {'quad_pixel_uv':raw.tolist(),'pixel_uv':centre.tolist(),'mask_quad_iou':float(agreement),
            'units':'raw_pixels','method':'NEURAL_TOP_MASK_INDEPENDENT_EDGE_LINES_DIAGONALS',
            'metric_localization_verified':False,'physical_execution':False}


def associate_neural_mask(mask,offset,box,shape=None):
    """Discard whole components disjoint from the target detection, never clip a top."""
    if not isinstance(mask,np.ndarray) or mask.ndim!=2 or mask.dtype!=np.uint8:
        raise ValueError('Binary uint8 neural mask required')
    offset=np.asarray(offset,float);box=np.asarray(box,float)
    if offset.shape!=(2,) or box.shape!=(4,) or not np.isfinite(np.r_[offset,box]).all() or np.any(box[2:]<=box[:2]):
        raise ValueError('Finite positive detector box and two-dimensional offset required')
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask)
    low=np.maximum(np.floor(box[:2]-offset),0).astype(int)
    high=np.minimum(np.ceil(box[2:]-offset),[mask.shape[1],mask.shape[0]]).astype(int)
    touching=set(np.unique(labels[low[1]:high[1],low[0]:high[0]])) if np.all(high>low) else set()
    output=mask.copy();removed=[]
    for j in range(1,n):
        if j not in touching:
            output[labels==j]=0
            removed.append({'area_px':int(stats[j,cv2.CC_STAT_AREA]),'reason':'COMPONENT_DISJOINT_FROM_TARGET_BOX'})
        elif shape in ('circle','square','rectangle') and stats[j,cv2.CC_STAT_AREA]>=100:
            # A padded bottle ROI may also contain a separate reflection from
            # a neighbouring object. Keep every complete, qualifying circle;
            # two qualifying shapes remain ambiguous. Never clip a component
            # or choose by size/confidence to manufacture a valid cap.
            component=np.where(labels==j,255,0).astype(np.uint8)
            if pixel_surface(component,offset,box,shape) is None:
                output[labels==j]=0
                removed.append({'area_px':int(stats[j,cv2.CC_STAT_AREA]),
                                'reason':'COMPONENT_INCONSISTENT_WITH_REGISTERED_'+shape.upper()})
    retained=sum(int(j in touching and stats[j,cv2.CC_STAT_AREA]>=100
                     and np.any(output[labels==j])) for j in range(1,n))
    return output,{'method':'WHOLE_COMPONENT_TARGET_BOX_INTERSECTION_NO_PIXEL_CLIPPING',
                   'removed_components':removed,
                   'registered_shape':shape,
                   'circle_component_gate':'EXISTING_PIXEL_SURFACE_ELLIPSE_IOU_0_85' if shape=='circle' else None,
                   'quad_component_gate':'CONTOUR_OR_INDEPENDENT_LINES_IOU_0_85' if shape in ('square','rectangle') else None,
                   'retained_significant_components':retained,
                   'mask_pixels_clipped_to_box':False}


def contour_mask(mask):
    if not isinstance(mask,np.ndarray) or mask.ndim!=2 or mask.dtype!=np.uint8:
        raise ValueError('Binary uint8 neural mask required')
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask)
    valid=[j for j in range(1,n) if stats[j,cv2.CC_STAT_AREA]>=100]
    if len(valid)!=1:return None
    clean=np.where(labels==valid[0],255,0).astype(np.uint8)
    contours,_=cv2.findContours(clean,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    c=contours[0];x,y,w,h=cv2.boundingRect(c)
    if x<=1 or y<=1 or x+w>=mask.shape[1]-1 or y+h>=mask.shape[0]-1:return None
    return clean,c


def pixel_surface(mask,offset,box,shape):
    found=contour_mask(mask)
    if found is None:return None
    clean,c=found
    if shape in ('square','rectangle'):
        fit=fit_registered_quad(clean,offset,box)
        if fit:return {**fit,'shape':shape,'physical_execution':False}
        return None
    if shape!='circle':raise ValueError('Unknown registered shape')
    if len(c)<5:return None
    ellipse=cv2.fitEllipse(c)
    display_centre=np.array(ellipse[0])+offset
    if (np.any(display_centre<np.asarray(box[:2])) or
            np.any(display_centre>np.asarray(box[2:]))):return None
    fitted=np.zeros_like(clean);cv2.ellipse(fitted,ellipse,255,-1)
    overlap=np.count_nonzero((fitted>0)&(clean>0))/np.count_nonzero((fitted>0)|(clean>0))
    if overlap<.85:return None
    return {'shape':'circle','contour_pixel_uv':(c.reshape(-1,2)+offset).tolist(),
            'ellipse_display':{'centre_uv':(np.array(ellipse[0])+offset).tolist(),
                               'axes_wh':list(ellipse[1]),'angle_deg':ellipse[2]},
            'mask_ellipse_iou':float(overlap),'pixel_uv':None,
            'method':'NEURAL_TOP_CONTOUR_CIRCLE_CENTRE_REQUIRES_PLANE_PROJECTION',
            'metric_localization_verified':False,'physical_execution':False}


def metric_surface(mask,offset,box,rule,geometry):
    """geometry.project must undistort and intersect the registered top plane."""
    if rule.get('dimensions_verified') is not True or not isinstance(rule.get('dimensions_mm'),dict):
        raise ValueError('Measured object dimensions required')
    shape=rule['shape'];dims=rule['dimensions_mm'];z=float(dims['height'])
    if not np.isfinite(z) or z<=0:raise ValueError('Positive known height required')
    found=contour_mask(mask)
    if found is None:return None
    clean,c=found
    if shape in ('square','rectangle'):
        pixel=fit_registered_quad(clean,offset,box)
        if pixel is None:return None
        pts=np.array([geometry.project(p,z)[:2] for p in pixel['quad_pixel_uv']])
        if not np.isfinite(pts).all():return None
        edges=np.roll(pts,-1,axis=0)-pts;length=np.linalg.norm(edges,axis=1)
        if min(length)<1:return None
        cosine=np.sum(edges*np.roll(edges,-1,axis=0),axis=1)/(length*np.roll(length,-1))
        if np.max(np.abs(cosine))>.25:return None
        pair=np.array([(length[0]+length[2])/2,(length[1]+length[3])/2])
        expected=np.array([dims['side'],dims['side']] if shape=='square' else [dims['length'],dims['width']],float)
        if not np.isfinite(expected).all() or np.any(expected<=0):raise ValueError('Positive finite dimensions required')
        if np.any(np.abs(np.sort(pair)-np.sort(expected))/np.sort(expected)>.22):return None
        centre=np.mean(pts,axis=0)
        direction=edges[np.argmax(length)]
        long_yaw=float(np.degrees(np.arctan2(direction[1],direction[0]))%180)
        # Gripper closes across the short dimension. The controller still needs
        # its measured tool-axis convention before using this as a wrist angle.
        result={'centre_table_xyz_mm':[float(centre[0]),float(centre[1]),z],
                'quad_table_xy_mm':pts.tolist(),'measured_edge_lengths_mm':length.tolist(),
                'long_axis_yaw_mod180_deg':long_yaw,
                'closing_axis_yaw_mod180_deg':(long_yaw+90)%180,
                'orientation_period_deg':90 if shape=='square' else 180,
                'pixel_uv':pixel['pixel_uv']}
    elif shape=='circle':
        if pixel_surface(mask,offset,box,'circle') is None:return None
        contour=c.reshape(-1,2).astype(float)+offset
        # Bound computation while preserving the full perimeter.
        contour=contour[::max(1,len(contour)//160)]
        pts=np.array([geometry.project(p,z)[:2] for p in contour])
        if not np.isfinite(pts).all():return None
        origin=pts.mean(0);q=pts-origin
        matrix=np.column_stack((2*q,np.ones(len(q))))
        solution,_,rank,_=np.linalg.lstsq(matrix,(q*q).sum(1),rcond=None)
        if rank<3:return None
        centre=solution[:2]+origin
        radius2=solution[2]+solution[:2]@solution[:2]
        if radius2<=0:return None
        radius=np.sqrt(radius2);residual=np.abs(np.linalg.norm(pts-centre,axis=1)-radius)
        diameter=2*radius;expected=float(dims['top_diameter'])
        if (not np.isfinite(expected) or expected<=0 or abs(diameter-expected)/expected>.22 or
                np.percentile(residual,95)/radius>.09):return None
        result={'centre_table_xyz_mm':[float(centre[0]),float(centre[1]),z],
                'diameter_mm':float(diameter),'circle_residual_p95_mm':float(np.percentile(residual,95)),
                'closing_axis_yaw_mod180_deg':None,'orientation_period_deg':None,
                'yaw_policy':'AXISYMMETRIC_CHOOSE_REACHABLE_COLLISION_FREE_GRIP_DIRECTION',
                'pixel_uv':None}
    else:raise ValueError('Unknown registered shape')
    return {**result,'shape':shape,'method':'NEURAL_MASK_UNDISTORTED_KNOWN_HEIGHT_'+shape.upper(),
            'height_measured_from_rgb':False,'metric_localization_verified':False,
            'physical_execution':False,'robot_base_xyz_mm':None,'joint_path':None}
