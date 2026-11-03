"""Physical-plane rectangle residual for rounded eraser corner predictions."""
import numpy as np


def rectangle_residual(points):
    points=np.asarray(points,dtype=float)
    if points.shape not in ((4,2),(4,3)) or not np.isfinite(points).all():
        raise ValueError('Four finite ordered physical-plane corners required')
    p=points[:,:2];edges=np.roll(p,-1,axis=0)-p
    cross=edges[:,0]*np.roll(edges,-1,axis=0)[:,1]-edges[:,1]*np.roll(edges,-1,axis=0)[:,0]
    if not (np.all(cross>1e-6) or np.all(cross< -1e-6)):
        raise ValueError('Convex ordered eraser corners required')
    centre=p.mean(0)
    a=(p[1]+p[2]-p[0]-p[3])/4;b=(p[2]+p[3]-p[0]-p[1])/4
    u,_,vt=np.linalg.svd(np.column_stack((a,b)));axes=u@vt
    half=np.array([a@axes[:,0],b@axes[:,1]])
    fitted=centre+(np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*half)@axes.T
    error=np.linalg.norm(fitted-p,axis=1)
    return {'centre_xy_mm':centre.tolist(),'fitted_size_mm':(2*half).tolist(),
        'maximum_corner_residual_mm':float(error.max()),'within2mm':bool(error.max()<=2),
        'raw_four_corner_centre_retained':True,'raw_corners_replaced':False}
