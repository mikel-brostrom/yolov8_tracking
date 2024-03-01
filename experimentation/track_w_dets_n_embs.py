# Mikel Broström 🔥 Yolo Tracking 🧾 AGPL-3.0 license

import argparse
from pathlib import Path
import numpy as np
from functools import partial
import json
import torch

from tqdm import tqdm

from boxmot import TRACKERS
from boxmot.tracker_zoo import create_tracker

from boxmot.utils import ROOT, WEIGHTS, TRACKER_CONFIGS
from boxmot.utils.checks import TestRequirements
from examples.detectors import get_yolo_inferer
from boxmot.appearance.reid_multibackend import ReIDDetectMultiBackend
from boxmot.utils import logger as LOGGER

from ultralytics.data.loaders import LoadImages
from ultralytics import YOLO
from ultralytics.data.utils import VID_FORMATS

from examples.utils import write_np_mot_results


__tr = TestRequirements()
__tr.check_packages(('ultralytics @ git+https://github.com/mikel-brostrom/ultralytics.git', ))  # install


@torch.no_grad()
def run(args):

    tracker = create_tracker(
        args.tracking_method,
        TRACKER_CONFIGS / (args.tracking_method + '.yaml'),
        args.reid_model,
        'cpu',
        args.half,
        args.per_class
    )

    with open(args.dets_n_embs_file_path, 'r') as file:
        header = file.readline().strip().replace("# ", "")  # .strip() removes leading/trailing whitespace and newline characters

    args.source = header
    dets_n_embs = np.loadtxt(args.dets_n_embs_file_path, skiprows=1)  # skiprows=1 skips the header row

    dataset = LoadImages(args.source)
    for frame_idx, d in enumerate(tqdm(dataset)):

        im = d[1][0]

        # get dets and embedding associated to this frame
        frame_dets_n_embs = dets_n_embs[dets_n_embs[:, 0] == frame_idx + 1]

        # frame id, x1, y1, x2, y2, conf, cls
        dets = frame_dets_n_embs[:, 1:7]
        embs = frame_dets_n_embs[:, 7:]
        tracks = tracker.update(dets, im, embs)

        p = args.project / args.name / 'mot' / (Path(args.source).parent.name + '.txt')

        write_np_mot_results(
            p,
            tracks,
            frame_idx + 1,
        )


def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--yolo-model', type=Path, default=WEIGHTS / 'yolov8n',
                        help='yolo model path')
    parser.add_argument('--reid-model', type=Path, default=WEIGHTS / 'osnet_x0_25_msmt17.pt',
                        help='reid model path')
    parser.add_argument('--tracking-method', type=str, default='deepocsort',
                        help='deepocsort, botsort, strongsort, ocsort, bytetrack')
    parser.add_argument('--source', type=str, default='0',
                        help='file/dir/URL/glob, 0 for webcam')
    parser.add_argument('--imgsz', '--img', '--img-size', nargs='+', type=int, default=[640],
                        help='inference size h,w')
    parser.add_argument('--conf', type=float, default=0.5,
                        help='confidence threshold')
    parser.add_argument('--iou', type=float, default=0.7,
                        help='intersection over union (IoU) threshold for NMS')
    parser.add_argument('--device', default='',
                        help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--show', action='store_true',
                        help='display tracking video results')
    parser.add_argument('--save', action='store_true',
                        help='save video tracking results')
    # class 0 is person, 1 is bycicle, 2 is car... 79 is oven
    parser.add_argument('--classes', nargs='+', type=int, default=0,
                        help='filter by class: --classes 0, or --classes 0 2 3')
    parser.add_argument('--project', default=ROOT / 'runs' / 'track',
                        help='save results to project/name')
    parser.add_argument('--name', default='exp',
                        help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', default=True,
                        help='existing project/name ok, do not increment')
    parser.add_argument('--half', action='store_true',
                        help='use FP16 half-precision inference')
    parser.add_argument('--vid-stride', type=int, default=1,
                        help='video frame-rate stride')
    parser.add_argument('--show-labels', action='store_false',
                        help='either show all or only bboxes')
    parser.add_argument('--show-conf', action='store_false',
                        help='hide confidences when show')
    parser.add_argument('--save-txt', action='store_true',
                        help='save tracking results in a txt file')
    parser.add_argument('--save-id-crops', action='store_true',
                        help='save each crop to its respective id folder')
    parser.add_argument('--save-mot', action='store_true',
                        help='save tracking results in a single txt file')
    parser.add_argument('--line-width', default=None, type=int,
                        help='The line width of the bounding boxes. If None, it is scaled to the image size.')
    parser.add_argument('--per-class', default=False, action='store_true',
                        help='not mix up classes when tracking')
    parser.add_argument('--verbose', default=True, action='store_true',
                        help='print results per frame')
    parser.add_argument('--agnostic-nms', default=False, action='store_true',
                        help='class-agnostic NMS')

    opt = parser.parse_args()
    return opt


if __name__ == "__main__":
    opt = parse_opt()
    dets_n_emb_file_paths = [item for item in (opt.project / opt.name / 'det_n_embs').glob('*.txt')]
    for dets_n_emb_file_path in dets_n_emb_file_paths:
        LOGGER.info(f"Started tracking on {dets_n_emb_file_path} with preloaded dets and embs")
        opt.dets_n_embs_file_path = dets_n_emb_file_path
        run(opt)