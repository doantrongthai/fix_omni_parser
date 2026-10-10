from util.utils import get_som_labeled_img, get_caption_model_processor, get_yolo_model, check_ocr_box
import torch
from PIL import Image
import io
import base64
from typing import Dict
class Omniparser(object):
    def __init__(self, config: Dict):
        self.config = config
        req_device = config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.device = 'cuda' if (req_device == 'cuda' and torch.cuda.is_available()) else 'cpu'

        self.som_model = get_yolo_model(model_path=config.get('som_model_path'), device=self.device)
        
        if config.get('use_local_semantics') is not None:
            self.use_semantics = bool(config['use_local_semantics'])
        else:
            # GPU (Colab): 100% original pipeline (True); CPU (Local): Fast mode (False)
            self.use_semantics = (self.device == 'cuda')

        if self.use_semantics:
            self.caption_model_processor = get_caption_model_processor(
                model_name=config['caption_model_name'], 
                model_name_or_path=config['caption_model_path'], 
                device=self.device
            )
        else:
            self.caption_model_processor = None
        print(f'Omniparser initialized on {self.device.upper()} (full_caption={self.use_semantics})!!!')

    def parse(self, image_base64: str):
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        print('image size:', image.size)
        
        box_overlay_ratio = max(image.size) / 3200
        draw_bbox_config = {
            'text_scale': 0.8 * box_overlay_ratio,
            'text_thickness': max(int(2 * box_overlay_ratio), 1),
            'text_padding': max(int(3 * box_overlay_ratio), 1),
            'thickness': max(int(3 * box_overlay_ratio), 1),
        }

        default_thresh = 0.05 if self.device == 'cuda' else 0.15
        box_thresh = self.config.get('BOX_TRESHOLD') or default_thresh

        (text, ocr_bbox), _ = check_ocr_box(image, display_img=False, output_bb_format='xyxy', easyocr_args={'text_threshold': 0.8}, use_paddleocr=False)
        dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image, self.som_model, BOX_TRESHOLD=box_thresh, 
            output_coord_in_ratio=True, ocr_bbox=ocr_bbox, draw_bbox_config=draw_bbox_config, 
            caption_model_processor=self.caption_model_processor, ocr_text=text, 
            use_local_semantics=self.use_semantics, iou_threshold=0.7, scale_img=False, batch_size=128
        )

        return dino_labled_img, parsed_content_list