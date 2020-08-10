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
from tabulate import tabulate

SIMILARITY_THRESHOLD = 95.0
client = boto3.client('textract')

def annotate_image(boudingBoxes, image, height, width):
    stream = io.BytesIO()

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

    for box in boudingBoxes:
        x, y = show_bounding_box_positions(height, width, box['boundingbox'], "ROTATE_0")
        if box['confidence'] >= SIMILARITY_THRESHOLD:
            draw.rectangle((x, y), fill=None, outline="#00ff00", width=8)
            draw.text(x, f"Conf: {box['confidence']}", font=font, fill=(255, 255, 0, 128))
        else:
            draw.rectangle((x, y), fill=None, outline="#ff0000", width=4)
            draw.text(x, f"Conf: {box['confidence']}", font=font, fill=(255, 255, 0, 128))

    return image

def get_tables(table_blocks, block_map_table):
    tables = {}
    for index, table in enumerate(table_blocks):
        tables[index] = generate_table(table, block_map_table, index +1)
        #csv += '\n\n'
    return tables

def generate_table(table_result, blocks_map, table_index):
    rows = get_rows_columns_map(table_result, blocks_map)

    table_id = 'Table_' + str(table_index)

    table = []
    
    for row_index, cols in rows.items():
        row = []
        for col_index, text in cols.items():
            row.append('{}'.format(text))
        table.append(row)
        
    return table

def get_rows_columns_map(table_result, blocks_map):
    rows = {}
    for relationship in table_result['Relationships']:
        if relationship['Type'] == 'CHILD':
            for child_id in relationship['Ids']:
                cell = blocks_map[child_id]
                if cell['BlockType'] == 'CELL':
                    row_index = cell['RowIndex']
                    col_index = cell['ColumnIndex']
                    if row_index not in rows:
                        # create new row
                        rows[row_index] = {}
                        
                    # get the text value
                    rows[row_index][col_index] = get_text(cell, blocks_map)
    return rows

def print_tables(tables):
    if len(tables) <= 0:
        return "<b> NO Table FOUND / OR SEARCHED </b>"
    else:   
        for index in tables:
            print(tabulate(tables[index]))
    print('\n\n')

def get_forms_relationship(key_map, value_map, block_map_forms):
    kvs = {}
    for block_id, key_block in key_map.items():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map_forms)
        val = get_text(value_block, block_map_forms)
        kvs[key] = val
    return kvs

def find_value_block(key_block, value_map):
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                value_block = value_map[value_id]
    return value_block

def get_text(result, blocks_map):
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '    

                                
    return text

def print_forms(kvs):
    if (len(kvs) > 0):
        print("\n\n== FOUND KEY : VALUE pairs ===\n")
        for key, value in kvs.items():
            print(key, ":", value)
        print('\n\n')

def get_Block_Informations(blockType, textract_resp):
    boudingBoxes = []
    lines = []

    #Get Key and Value Forms Maps
    key_map = {}
    value_map = {}
    block_map_forms = {}

    #Get table
    block_map_table = {}
    table_blocks = []

    for block in textract_resp['Blocks']:
        boundingBox = {}
        line = {}

        block_id = block['Id']
        block_map_forms[block_id] = block

        block_map_table[block['Id']] = block

        if (block['BlockType'] in str(blockType)):
            boundingBox['confidence'] = block['Confidence']
            boundingBox['boundingbox'] = block['Geometry']['BoundingBox']
            boudingBoxes.append(boundingBox)

            if (block['BlockType'] == 'LINE'):
                line['Text'] = block['Text']
                line['Confidence'] = block['Confidence']
                lines.append(line)

            if (block['BlockType'] == 'KEY_VALUE_SET'):
                if 'KEY' in block['EntityTypes']:
                    key_map[block_id] = block
                else:
                    value_map[block_id] = block

            if (block['BlockType'] == 'TABLE'):
                table_blocks.append(block)

    return boudingBoxes, lines, key_map, value_map, block_map_forms, block_map_table, table_blocks

def get_API_blockType (APItype, featureType):
    blockType = []
    if (APItype == 'detect_document_text'):
        blockType = ['LINE']

    if ((APItype == 'analyze_document') and (featureType == 'T')):
        blockType = ['TABLE', 'CELL']

    if ((APItype == 'analyze_document') and (featureType == 'F')):
        blockType = ['KEY_VALUE_SET']

    if ((APItype == 'analyze_document') and (featureType == 'A')):
        blockType = ['TABLE', 'CELL', 'KEY_VALUE_SET']

    return blockType

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
    
    text = ''

    #Get Image Information
    image = get_image_information(filename)
    width, height = image.size

    #Textract API Call
    if (APItype == 'analyze_document'): textract_resp = analyzeText(filename, featureType)
    else: textract_resp = extractText(filename)
    #print(textract_resp)

    #Extracting Useful informations on textract response
    blockType = get_API_blockType (APItype, featureType)
    boudingBoxes, lines, key_map, value_map, block_map_forms, block_map_table, table_blocks = get_Block_Informations(blockType, textract_resp)

    #Getting Lines and accuracy

    
    #Get Forms relationship
    key_value = get_forms_relationship(key_map, value_map, block_map_forms)
    print_forms(key_value)

    #Get tables relationships
    tables = get_tables(table_blocks, block_map_table)
    print_tables(tables)

    image = annotate_image (boudingBoxes, image, height, width)
    image.show()

if __name__ == "__main__":
    filename = sys.argv[1]
    APItype = sys.argv[2]
    if(APItype == 'detect_document_text'): featureType = ''
    else: featureType = sys.argv[3]

    main(filename, APItype, featureType)