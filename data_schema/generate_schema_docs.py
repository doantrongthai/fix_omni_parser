#!/usr/bin/env python3
import json
import os
import base64
from PIL import Image

output_dir = "/home/thai/Downloads/omniparser/data_schema"
schemas_dir = os.path.join(output_dir, "schemas")
examples_dir = os.path.join(output_dir, "examples")
os.makedirs(schemas_dir, exist_ok=True)
os.makedirs(examples_dir, exist_ok=True)

# 1. Step 1: Screen Capture
step1_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step1_ScreenCaptureResponse",
    "description": "Schema for screen capture output from Host Server (Linux / Windows)",
    "type": "object",
    "required": ["status", "width", "height", "screenshot_uuid", "base64_image"],
    "properties": {
        "status": {"type": "string", "enum": ["success", "error"]},
        "width": {"type": "integer", "description": "Screen width in physical pixels"},
        "height": {"type": "integer", "description": "Screen height in physical pixels"},
        "scale_factor": {"type": "number", "description": "Display scaling factor (e.g. 1.0 or 1.25)"},
        "screenshot_uuid": {"type": "string", "format": "uuid"},
        "base64_image": {"type": "string", "description": "Raw screenshot image encoded as Base64 PNG"},
        "timestamp": {"type": "number", "description": "Unix timestamp in seconds"}
    }
}

step1_example = {
    "status": "success",
    "width": 1920,
    "height": 1080,
    "scale_factor": 1.0,
    "screenshot_uuid": "e4b29c11-7362-4b77-8fa2-03915f79a9d2",
    "base64_image": "iVBORw0KGgoAAAANSUhEUgAAB4AAAAQ4CAYAAABv2i9vAAA...[TRUNCATED_BASE64_PNG]",
    "timestamp": 1728639100.125
}

# 2. Step 2: OmniParser Request
step2_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step2_OmniParserParseRequest",
    "description": "Schema for HTTP POST /parse/ request sent to OmniParser FastAPI server",
    "type": "object",
    "required": ["base64_image"],
    "properties": {
        "base64_image": {
            "type": "string",
            "description": "Base64 encoded string of the desktop screenshot"
        }
    }
}

step2_example = {
    "base64_image": "iVBORw0KGgoAAAANSUhEUgAAB4AAAAQ4CAYAAABv2i9vAAA...[TRUNCATED_BASE64_PNG]"
}

# 3. Step 3: YOLO Detection
step3_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step3_YoloIconDetections",
    "description": "Intermediate schema of icon/button bounding boxes detected by YOLOv8/v9",
    "type": "object",
    "required": ["model_version", "box_threshold", "detections"],
    "properties": {
        "model_version": {"type": "string"},
        "box_threshold": {"type": "number"},
        "total_detected": {"type": "integer"},
        "detections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["bbox_normalized", "confidence", "class_id", "label"],
                "properties": {
                    "bbox_normalized": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[xmin, ymin, xmax, ymax] normalized to [0, 1]"
                    },
                    "confidence": {"type": "number"},
                    "class_id": {"type": "integer"},
                    "label": {"type": "string"}
                }
            }
        }
    }
}

step3_example = {
    "model_version": "microsoft/OmniParser-v2.0-yolov8x",
    "box_threshold": 0.05,
    "total_detected": 4,
    "detections": [
        {
            "bbox_normalized": [0.354, 0.021, 0.621, 0.058],
            "confidence": 0.92,
            "class_id": 0,
            "label": "icon"
        },
        {
            "bbox_normalized": [0.625, 0.021, 0.655, 0.058],
            "confidence": 0.88,
            "class_id": 0,
            "label": "icon"
        },
        {
            "bbox_normalized": [0.015, 0.018, 0.075, 0.062],
            "confidence": 0.95,
            "class_id": 0,
            "label": "icon"
        },
        {
            "bbox_normalized": [0.945, 0.018, 0.985, 0.062],
            "confidence": 0.84,
            "class_id": 0,
            "label": "icon"
        }
    ]
}

# 4. Step 4: OCR Text Detection
step4_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step4_OcrExtractionResults",
    "description": "Intermediate schema of text regions extracted by EasyOCR / PaddleOCR",
    "type": "object",
    "required": ["engine", "text_threshold", "extracted_texts"],
    "properties": {
        "engine": {"type": "string", "enum": ["easyocr", "paddleocr"]},
        "text_threshold": {"type": "number"},
        "extracted_texts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "bbox_normalized", "confidence"],
                "properties": {
                    "text": {"type": "string"},
                    "bbox_normalized": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[xmin, ymin, xmax, ymax] normalized to [0, 1]"
                    },
                    "confidence": {"type": "number"}
                }
            }
        }
    }
}

step4_example = {
    "engine": "easyocr",
    "text_threshold": 0.8,
    "extracted_texts": [
        {
            "text": "Search",
            "bbox_normalized": [0.380, 0.026, 0.435, 0.052],
            "confidence": 0.97
        },
        {
            "text": "DeepMind Robotics",
            "bbox_normalized": [0.120, 0.150, 0.285, 0.180],
            "confidence": 0.94
        },
        {
            "text": "Subscriptions",
            "bbox_normalized": [0.012, 0.220, 0.090, 0.245],
            "confidence": 0.99
        }
    ]
}

# 5. Step 5: OmniParser Final Response
step5_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step5_OmniParserResponse",
    "description": "Schema for HTTP POST /parse/ response from OmniParser server",
    "type": "object",
    "required": ["som_image_base64", "parsed_content_list", "latency"],
    "properties": {
        "som_image_base64": {
            "type": "string",
            "description": "Base64 encoded Set-of-Mark annotated PNG image with labeled boxes and ID tags"
        },
        "parsed_content_list": {
            "type": "array",
            "description": "Ordered list of detected screen UI elements corresponding to Box IDs",
            "items": {
                "type": "object",
                "required": ["type", "bbox", "interactivity", "content"],
                "properties": {
                    "type": {"type": "string", "enum": ["text", "icon"]},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[ymin, xmin, ymax, xmax] normalized coordinates [0, 1]"
                    },
                    "interactivity": {"type": "boolean"},
                    "content": {"type": ["string", "null"]},
                    "source": {"type": "string"}
                }
            }
        },
        "latency": {
            "type": "number",
            "description": "Processing time in seconds"
        }
    }
}

step5_example = {
    "som_image_base64": "iVBORw0KGgoAAAANSUhEUgAAB4AAAAQ4CAYAAABv2i9vAAA...[TRUNCATED_SOM_ANNOTATED_BASE64]",
    "parsed_content_list": [
        {
            "type": "text",
            "bbox": [0.026, 0.380, 0.052, 0.435],
            "interactivity": False,
            "content": "Search",
            "source": "box_ocr_content_ocr"
        },
        {
            "type": "icon",
            "bbox": [0.021, 0.354, 0.058, 0.621],
            "interactivity": True,
            "content": "YouTube search input box with placeholder Search",
            "source": "box_yolo_content_florence"
        },
        {
            "type": "icon",
            "bbox": [0.021, 0.625, 0.058, 0.655],
            "interactivity": True,
            "content": "magnifying glass search button icon",
            "source": "box_yolo_content_florence"
        },
        {
            "type": "icon",
            "bbox": [0.018, 0.015, 0.062, 0.075],
            "interactivity": True,
            "content": "YouTube red play logo button",
            "source": "box_yolo_content_florence"
        }
    ],
    "latency": 1.482
}

# 6. Step 6: LLM Agent Decision
step6_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step6_LLMAgentActionDecision",
    "description": "Schema of the structured decision output by Multimodal LLM (DeepSeek-R1 / Groq / OpenAI)",
    "type": "object",
    "required": ["Reasoning", "Next Action"],
    "properties": {
        "Reasoning": {
            "type": "string",
            "description": "Detailed reasoning explaining current screen context and the logical rationale for the chosen action"
        },
        "Next Action": {
            "type": "string",
            "description": "Action name and description: left_click, type, right_click, double_click, hover, scroll_down, scroll_up, wait, or None"
        },
        "Box ID": {
            "type": ["integer", "null"],
            "description": "Target numeric Box ID identified from the SoM annotated image"
        },
        "value": {
            "type": "string",
            "description": "String text value to type into the targeted input element (required if Next Action is 'type')"
        }
    }
}

step6_example = {
    "Reasoning": "The current screen shows YouTube homepage. To complete the user instruction 'Click vào thanh tìm kiếm trên màn hình, gõ DeepMind Robotics và nhấn Enter', I first need to click on the YouTube search input bar (Box ID 1) to focus cursor.",
    "Next Action": "left_click",
    "Box ID": 1
}

# 7. Step 7: Host Execution Request & Response
step7_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Step7_HostExecutionDispatch",
    "description": "Schema for hardware action execution request sent to Linux / Windows Host Server",
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["mouse_click", "double_click", "right_click", "mouse_move", "type", "press_key", "scroll"]
        },
        "point": {
            "type": "array",
            "items": {"type": "integer"},
            "minItems": 2,
            "maxItems": 2,
            "description": "[x, y] absolute physical screen coordinates calculated from Box ID center"
        },
        "text": {
            "type": "string",
            "description": "Text content to type into OS keyboard stream"
        },
        "key": {
            "type": "string",
            "description": "Special key name such as 'enter', 'tab', 'backspace', 'esc'"
        },
        "clicks": {
            "type": "integer"
        }
    }
}

step7_example = {
    "action": "mouse_click",
    "point": [936, 42],
    "text": None,
    "key": None,
    "clicks": 1
}

schemas = {
    "step1_screen_capture.schema.json": step1_schema,
    "step2_omniparser_request.schema.json": step2_schema,
    "step3_yolo_detections.schema.json": step3_schema,
    "step4_ocr_results.schema.json": step4_schema,
    "step5_omniparser_response.schema.json": step5_schema,
    "step6_llm_agent_decision.schema.json": step6_schema,
    "step7_host_action_execution.schema.json": step7_schema
}

examples = {
    "step1_screen_capture.example.json": step1_example,
    "step2_omniparser_request.example.json": step2_example,
    "step3_yolo_detections.example.json": step3_example,
    "step4_ocr_results.example.json": step4_example,
    "step5_omniparser_response.example.json": step5_example,
    "step6_llm_agent_decision.example.json": step6_example,
    "step7_host_action_execution.example.json": step7_example
}

for filename, schema in schemas.items():
    with open(os.path.join(schemas_dir, filename), "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

for filename, example in examples.items():
    with open(os.path.join(examples_dir, filename), "w", encoding="utf-8") as f:
        json.dump(example, f, indent=2, ensure_ascii=False)

print("Generated all schemas and examples successfully!")

