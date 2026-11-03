"""Quark conversion for the frozen six-class model and TRAIN-only spatial views.

Run in the target Ryzen AI SDK environment. No SDK/API compatibility is claimed
until it has actually run on that host. Unsupported combinations fail explicitly.
"""
from copy import deepcopy
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.deployment import inside, load_inputs, save
from pc.mode_b.tiled_detector import square_views
from pc.multiobject.dataset import read_image
from pc.multiobject.yolo import digest, load_package, prepare


def calibration_views(inputs, root):
    data = load_inputs(inputs, root)
    for row in data['calibration']['items']:
        image = read_image(inside(root, row['image']))
        for view in [None]+square_views(*row['image_size_wh']):
            yield row, image, view


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', type=Path, default=ROOT/'handoff/inputs.json')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--precision', choices=['BF16', 'XINT8'], default='BF16')
    a = p.parse_args()
    if a.out.exists():
        p.error('Fresh quantization output required')
    data = load_inputs(a.inputs, ROOT)
    package = inside(ROOT, data['detector'])
    spec, model = load_package(package)
    # Import SDK only after content and split checks; never use replay for calibration.
    import onnx
    from onnxruntime.quantization import CalibrationDataReader
    from quark.onnx import ModelQuantizer
    from quark.onnx.quantization.config.config import Config
    from quark.onnx.quantization.config.custom_config import get_default_config
    name = onnx.load(model).graph.input[0].name

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.rewind()

        def rewind(self):
            self.iterator = iter(calibration_views(a.inputs, ROOT))

        def get_next(self):
            next_view = next(self.iterator, None)
            if next_view is None:
                return None
            _, image, view = next_view
            return {name: prepare(image, spec['input_size_wh'], view)[0]}

    config = deepcopy(get_default_config(a.precision))
    if a.precision == 'BF16':
        config.extra_options['BF16QDQToCast'] = True
    a.out.mkdir(parents=True)
    try:
        ModelQuantizer(Config(global_quant_config=config)).quantize_model(
            str(model), str(a.out/'model.onnx'), Reader())
        views = [{'image_sha256': row['image_sha256'], 'roi_xywh_raw': view}
                 for row, _, view in calibration_views(a.inputs, ROOT)]
        result = deepcopy(spec)
        result.update(precision=a.precision.lower(),
                      onnx={'file': 'model.onnx', 'sha256': digest(a.out/'model.onnx')},
                      float_source_sha256=digest(model),
                      deployment_inputs_sha256=digest(a.inputs),
                      quark_version=importlib.metadata.version('amd-quark'),
                      calibration={'split': 'train', 'views': views, 'replay_used': False},
                      npu_validation='NOT_RUN_COMPILATION_REQUIRED')
        save(a.out/'model.json', result)
        load_package(a.out/'model.json')
    except Exception as exc:
        save(a.out/'conversion_error.json', {'status': 'ERROR', 'error': str(exc),
                                          'physical_execution': False})
        raise
    print('CONVERTED_NOT_NPU_ACCEPTED', a.out)


if __name__ == '__main__':
    main()
