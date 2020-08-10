import boto3
import os
import json
import random
import numpy as np
import boto3
import string
from PIL import Image, ImageDraw, ImageFont
import io
import sys
import uuid
import re
import time

SIMILARITY_THRESHOLD = 95.0
client = boto3.client('textract')

def annotate_image(textract_resp, image, height, width, APItype, featureType):
    stream = io.BytesIO()

    text = {
        'document_text': []
    }

    if 'exif' in image.info:
        exif = image.info['exif']
        image.save(stream, format=image.format, exif=exif)
    else:
        image.save(stream, format=image.format)

    draw = ImageDraw.Draw(image)
    font = None

    try:
        font = ImageFont.truetype("Arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

        
    blockType = []
    if (APItype == 'detect_document_text'):
        blockType = ['LINE']

    if ((APItype == 'analyze_document') and (featureType == 'T')):
        blockType = ['TABLE', 'CELL']

    if ((APItype == 'analyze_document') and (featureType == 'F')):
        blockType = ['KEY_VALUE_SET']

    for block in textract_resp['Blocks']:
        if (block['BlockType'] in str(blockType)):
            confidence = block['Confidence']
            boundingbox = block['Geometry']['BoundingBox']
            
            if (block['BlockType'] == 'LINE'):
                blockJson = {
                    'Text': block['Text'],
                    'Confidence': block['Confidence']
                }
                text['document_text'].append(blockJson)

            x, y = show_bounding_box_positions(height, width, boundingbox, "ROTATE_0")

            if confidence >= SIMILARITY_THRESHOLD:
                draw.rectangle((x, y), fill=None, outline="#00ff00", width=8)
                draw.text(x, f"Conf: {confidence}", font=font, fill=(255, 255, 0, 128))
            else:
                draw.rectangle((x, y), fill=None, outline="#ff0000", width=4)
                draw.text(x, f"Conf: {confidence}", font=font, fill=(255, 255, 0, 128))


    return image, text

def get_image_information(photo): 

    #Get image width and height
    image = Image.open(open(photo,'rb'))
    width, height = image.size
    
    return image

def show_bounding_box_positions(image_height, image_width, box, rotation):
    left = 0
    top = 0
      
    if rotation == 'ROTATE_0':
        left = image_width * box['Left']
        top = image_height * box['Top']
    
    if rotation == 'ROTATE_90':
        left = image_height * (1 - (box['Top'] + box['Height']))
        top = image_width * box['Left']

    if rotation == 'ROTATE_180':
        left = image_width - (image_width * (box['Left'] + box['Width']))
        top = image_height * (1 - (box['Top'] + box['Height']))

    if rotation == 'ROTATE_270':
        left = image_height * box['Top']
        top = image_width * (1 - box['Left'] - box['Width'] )

    return (left, top), (left + image_width * box['Width'], top + image_height * box['Height'])


def extractText (photo):
    with open(photo, 'rb') as image:
        response = client.detect_document_text(
            Document={
                'Bytes': image.read()
                }
            )
    
    return response


def analyzeText (photo, featureType):
    featureTypes = []
    if(featureType == 'T'):
        featureTypes = ['TABLES']
    if(featureType == 'F'):
        featureTypes = ['FORMS']
    if(featureType == 'A'):
        featureTypes = ['TABLES', 'FORMS']


    with open(photo, 'rb') as image:
        response = client.analyze_document(
            Document={
                'Bytes': image.read()
                },
            FeatureTypes= featureTypes
        )
    return response

def main(filename, APItype, featureType):
    
    text = {}
    
    #Get Image Information
    image = get_image_information(filename)
    width, height = image.size

    #Textract API Call
    if (APItype == 'analyze_document'): textract_resp = analyzeText(filename, featureType)
    else: textract_resp = extractText(filename)
    #print(textract_resp)

    image, text = annotate_image (textract_resp, image, height, width, APItype, featureType)
    image.show()

if __name__ == "__main__":
    filename = sys.argv[1]
    APItype = sys.argv[2]
    if(APItype == 'detect_document_text'): featureType = ''
    else: featureType = sys.argv[3]

    main(filename, APItype, featureType)