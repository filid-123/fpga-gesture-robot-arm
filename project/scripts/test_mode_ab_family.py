"""Verify proof binding and conservative payload/tilt rejection; no devices."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.family import certificate


class Tests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'candidate/mode_ab/profiles/red_depth12'
        self.c=json.loads((folder/'normal.json').read_bytes());self.p=json.loads((folder/'native_bank1.json').read_bytes())

    def test_reference_and_small_rigid_perturbation_are_certified(self):
        self.assertIsNotNone(certificate(self.c,self.p))
        self.p['tcp_from_object'][0][3]+=.1
        self.assertIsNotNone(certificate(self.c,self.p))

    def test_changed_tables_scene_model_or_class_cannot_reuse_proof(self):
        for kind in ('table','obstacle','margin','class','tilt','model','adapter','contact_phase'):
            c=deepcopy(self.c);p=deepcopy(self.p)
            if kind=='table':c['keypoint_banks'][0][0][0]+=1
            if kind=='obstacle':p['request']['obstacles']=[dict(id='new',centre_mm=[600,300,100],size_mm=[10,10,10])]
            if kind=='margin':p['local_scene_config']['collision_margin_mm']+=.1
            if kind=='class':p['request']['object_class']='eraser'
            if kind=='tilt':p['commissioning_tolerance_profile']['loaded_pitch_limit_from_vertical_deg']+=1
            if kind=='model':p['link5_from_local_object_tcp'][0][3]+=.1
            if kind=='adapter':p['object_adapter']['closed_rad']+=.01
            if kind=='contact_phase':p['stationary_source_phases'].append('HAND_CLEAR_FAMILY')
            self.assertIsNone(certificate(c,p),kind)

    def test_excessive_attachment_displacement_rotation_or_invalid_matrix_falls_back(self):
        for kind in ('distance','rotation','nonrigid','nan'):
            p=deepcopy(self.p)
            if kind=='distance':p['tcp_from_object'][0][3]+=100
            if kind=='rotation':
                from scipy.spatial.transform import Rotation
                a=np.array(p['tcp_from_object']);a[:3,:3]=Rotation.from_euler('x',30,degrees=True).as_matrix()@a[:3,:3];p['tcp_from_object']=a.tolist()
            if kind=='nonrigid':p['tcp_from_object'][0][0]*=2
            if kind=='nan':p['tcp_from_object'][0][0]=float('nan')
            self.assertIsNone(certificate(self.c,p),kind)


if __name__=='__main__':unittest.main()
