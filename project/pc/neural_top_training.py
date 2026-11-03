"""Session-isolated real/synthetic training augmentation for TinyTopNet.

Synthetic textures/backgrounds are derived only from TRAIN items. No HSV labels
are generated at inference or on the held-out images.
"""
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
from pc.neural_top_dataset import load_dataset, read_image


class BootstrapTraining(Dataset):
    def __init__(self, manifest, length=4096, seed=20261025, side=160):
        self.manifest = Path(manifest)
        self.data = load_dataset(manifest)
        self.items = [x for x in self.data['items'] if x['split'] == 'train']
        if not self.items:
            raise ValueError('No train sessions')
        self.images = [read_image(self.manifest.parent/x['image']) for x in self.items]
        self.masks = [read_image(self.manifest.parent/x['mask'], 0) for x in self.items]
        self.textures = {k: [] for k in (1, 2, 3)}
        self.backgrounds = []
        for item, im, mask in zip(self.items, self.images, self.masks):
            for obj in item['objects']:
                poly = np.asarray(obj['polygon_raw'], np.float32)
                transform = cv2.getPerspectiveTransform(poly, np.array([[0,0],[63,0],[63,63],[0,63]],np.float32))
                texture = cv2.warpPerspective(im, transform, (64,64))[4:-4, 4:-4]
                self.textures[obj['object_id']].append(texture)
            # Inpaint TRAIN tops/sides/shadows, then use only the central cloth crop.
            expanded = cv2.dilate((mask>0).astype(np.uint8), np.ones((65,65),np.uint8))
            clean = cv2.inpaint(im, expanded, 7, cv2.INPAINT_TELEA)
            self.backgrounds.append(clean[120:920, 300:1450])
        if any(not self.textures[k] for k in (1,2,3)):
            raise ValueError('Train data must contain each active class')
        self.length, self.seed, self.side = length, seed, side

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        rng = np.random.default_rng(self.seed+int(index))
        side = self.side
        if rng.random() < .35:
            idx = int(rng.integers(len(self.images)))
            image, mask = self.images[idx], self.masks[idx]
            # Random crop frequently centred on a labelled top, sometimes pure background.
            crop = int(rng.integers(270, 1100))
            if rng.random() < .8:
                obj = self.items[idx]['objects'][int(rng.integers(len(self.items[idx]['objects'])))]
                centre = np.mean(obj['polygon_raw'], axis=0)+rng.uniform(-crop*.25,crop*.25,2)
                x, y = np.rint(centre-crop/2).astype(int)
            else:
                x, y = int(rng.integers(0,1920-crop+1)), int(rng.integers(0,max(1,1080-crop+1)))
            x, y = max(0,min(x,image.shape[1]-crop)), max(0,min(y,image.shape[0]-crop))
            image = cv2.resize(image[y:y+crop,x:x+crop],(side,side))
            mask = cv2.resize(mask[y:y+crop,x:x+crop],(side,side),interpolation=cv2.INTER_NEAREST)
        else:
            bg = self.backgrounds[int(rng.integers(len(self.backgrounds)))]
            image = cv2.resize(bg,(side,side)).astype(np.float32)
            mask = np.zeros((side,side),np.uint8)
            # Tape-like distractors remain background. Active classes have top labels.
            for _ in range(int(rng.integers(0,4))):
                x,y = rng.integers(0,side,2)
                grey = float(rng.uniform(40,220))
                cv2.line(image,(int(x),0),(int(y),side-1),(grey,grey,grey),int(rng.integers(1,5)))
            occupied = []
            for k in rng.permutation([1,2,3])[:int(rng.integers(0,4))]:
                size = float(rng.uniform(side*.12,side*.35))
                centre = rng.uniform(size*.9,side-size*.9,2)
                if any(np.linalg.norm(centre-c)<size*.9+s*.8 for c,s in occupied):
                    continue
                occupied.append((centre,size))
                angle = rng.uniform(-180,180)
                poly = cv2.boxPoints((tuple(centre),(size,size),float(angle))).astype(np.float32)
                texture = self.textures[int(k)][int(rng.integers(len(self.textures[int(k)])))]
                # Preserve hue with broad intensity/white balance, avoid class swapping.
                texture = texture.astype(np.float32)*rng.uniform(.5,4.5)
                texture *= rng.uniform(.8,1.2,(1,1,3))
                texture = np.clip(texture,0,255).astype(np.uint8)
                texh,texw = texture.shape[:2]
                mat = cv2.getPerspectiveTransform(np.array([[0,0],[texw-1,0],[texw-1,texh-1],[0,texh-1]],np.float32),poly)
                top = cv2.warpPerspective(texture,mat,(side,side))
                region = np.zeros((side,side),np.uint8)
                cv2.fillConvexPoly(region,np.rint(poly).astype(np.int32),1)
                # Dark painted side and cast shadow; neither belongs to the top label.
                shift = rng.uniform(1,8,2)
                side_mask = np.zeros_like(region)
                cv2.fillConvexPoly(side_mask,
                                  cv2.convexHull(np.rint(np.vstack((poly,poly+shift))).astype(np.int32)),1)
                mean = np.mean(texture,axis=(0,1))*.22
                image[side_mask>0] = mean
                image[region>0] = top[region>0]
                mask[region>0] = int(k)
            image = np.clip(image,0,255).astype(np.uint8)
        # Photometric augmentation applied after target composition; labels unchanged.
        image = image.astype(np.float32)/255.
        image = np.power(np.clip(image,0,1),rng.uniform(.55,1.5))*rng.uniform(.65,1.8)
        image *= rng.uniform(.85,1.15,(1,1,3))
        image += rng.normal(0,rng.uniform(.002,.025),image.shape)
        image = np.clip(image,0,1).astype(np.float32)
        if rng.random()<.5:
            image, mask = image[:,::-1].copy(),mask[:,::-1].copy()
        if rng.random()<.5:
            image, mask = image[::-1].copy(),mask[::-1].copy()
        return torch.from_numpy(image[:,:,::-1].transpose(2,0,1).copy()),torch.from_numpy(mask.astype(np.int64))
