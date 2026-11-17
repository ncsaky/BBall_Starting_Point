"""Offline photographic segmentation and matting; never used by the game runtime.

Setup in a separate environment: pip install 'rembg[cpu]==2.0.85'
Run once to segment, then with --finish to matte, inspect proofs, and --publish.
The model predicts masks only. No image synthesis or generative filling is used.
"""
import sys
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from build_dot_press import ASSETS, ROOT, MASKS

WORK = ROOT / 'artifacts/dot-press/edge-refinement'


def coarse_mask(image, spec):
    mask = Image.new('L', image.size)
    pen = ImageDraw.Draw(mask)
    sx, sy = image.width/spec['ref'][0], image.height/spec['ref'][1]
    for poly in spec['polygons']:
        pen.polygon([(round(x*sx), round(y*sy)) for x,y in poly], fill=255)
    for box in spec.get('ellipses', []):
        pen.ellipse(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box)), fill=255)
    for poly in spec['holes']:
        pen.polygon([(round(x*sx), round(y*sy)) for x,y in poly], fill=0)
    return mask


def segment():
    from rembg import new_session
    session = new_session('birefnet-general-lite', providers=['CPUExecutionProvider'])
    for key,spec in MASKS.items():
        photo = Image.open(ASSETS/'sources'/spec['file']).convert('RGB')
        guide = coarse_mask(photo,spec)
        box = guide.getbbox()
        pad = round(photo.height*.035)
        box = (max(0,box[0]-pad),max(0,box[1]-pad),min(photo.width,box[2]+pad),min(photo.height,box[3]+pad))
        crop = photo.crop(box)
        prediction = session.predict(crop)[0]
        prediction = prediction.resize(crop.size,Image.Resampling.LANCZOS)
        alpha = Image.new('L',photo.size)
        alpha.paste(prediction,box[:2])
        alpha.save(WORK/f'{key}-prediction.png')
        result = photo.convert('RGBA');result.putalpha(alpha)
        result.save(WORK/f'{key}-predicted-cutout.png')
        print(f'Segmented {key}',flush=True)
    proof('predicted-cutout')


def proof(suffix):
    sheet = Image.new('RGB',(1600,1000),'#aab1b5')
    for i,key in enumerate(MASKS):
        if not (WORK/f'{key}-{suffix}.png').exists():
            continue
        photo=Image.open(WORK/f'{key}-{suffix}.png')
        box=coarse_mask(Image.open(ASSETS/'sources'/MASKS[key]['file']),MASKS[key]).getbbox()
        photo=photo.crop((max(0,box[0]-20),max(0,box[1]-20),box[2]+20,box[3]+20))
        photo.thumbnail((380,460),Image.Resampling.LANCZOS)
        for j,color in enumerate(['#f4f5f6','#131b20']):
            bg=Image.new('RGB',(400,500),color)
            bg.paste(photo,((400-photo.width)//2,(480-photo.height)//2),photo)
            ImageDraw.Draw(bg).text((12,480),key,fill='#8294a0')
            sheet.paste(bg,(i*400,j*500))
    sheet.save(WORK/f'{suffix}-proof.jpg',quality=95)


def finish():
    from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes
    from pymatting import estimate_alpha_cf, estimate_foreground_ml
    # Tight separation boundaries where foreground athletes touch other players.
    # Elsewhere the photographic segmentation supplies the edge, including hair/fingers.
    clips={
        'curry':[
            ((205,489,253,518),[(222,488),(251,488),(250,498),(247,508),(242,518),(217,518),(218,507),(220,497)]),
        ],
        'rodman-detroit':[
            ((285,423,479,650),[(423,422),(479,422),(469,433),(461,446),(455,460),(449,473),(442,487),(438,500),(438,513),(434,527),(428,541),(423,554),(418,563),(415,573),(415,585),(417,599),(418,611),(424,619),(430,625),(433,632),(430,637),(414,636),(399,634),(384,632),(369,628),(351,626),(335,622),(321,617),(310,611),(301,604),(298,598),(302,594),(313,594),(326,596),(338,593),(349,587),(360,578),(367,570),(369,566),(374,559),(378,548),(382,536),(386,521),(389,509),(395,510),(403,512),(405,499),(408,488),(411,477),(414,465),(417,452),(419,440)]),
            ((620,383,730,582),[(640,382),(699,382),(707,394),(708,409),(706,424),(702,439),(698,452),(691,466),(687,478),(688,487),(691,497),(695,510),(697,523),(696,538),(693,552),(687,565),(681,571),(674,570),(668,565),(663,556),(659,544),(656,530),(654,516),(653,501),(652,488),(651,480),(652,468),(655,455),(657,443),(655,430),(652,418),(646,402)]),
        ],
        'rodman-chicago':[
            ((287,449,410,592),[(335,448),(373,448),(374,460),(373,470),(371,480),(369,490),(367,497),(368,508),(369,517),(372,521),(373,531),(375,540),(376,550),(373,555),(377,563),(375,571),(368,576),(360,578),(349,576),(338,574),(327,570),(316,566),(307,562),(301,557),(298,551),(300,546),(306,548),(315,548),(323,545),(331,541),(337,536),(341,530),(344,522),(348,517),(350,507),(346,494),(342,480),(339,466)]),
        ],
        'allen':[
            ((635,1557,730,1610),[(662,1556),(716,1556),(720,1567),(722,1579),(722,1589),(718,1596),(710,1598),(696,1597),(683,1593),(674,1587),(668,1579),(664,1569)]),
        ],
    }
    erase={
        'rodman-detroit':[
            [(473,428),(479,422),(490,416),(501,410),(516,402),(533,393),(548,385),(563,375),(570,375),(570,427),(473,447)],
        ],
        'rodman-chicago':[
            [(374,444),(386,441),(402,441),(419,444),(437,446),(454,445),(466,443),(466,462),(374,462)],
            [(344,396),(350,391),(360,385),(377,382),(398,380),(398,387),(386,389),(374,391),(364,394),(354,397),(344,401)],
        ],
    }
    for key,spec in MASKS.items():
        photo=Image.open(ASSETS/'sources'/spec['file']).convert('RGB')
        guide=np.asarray(coarse_mask(photo,spec))>127
        pred=np.asarray(Image.open(WORK/f'{key}-prediction.png'))/255.
        sx,sy=photo.width/spec['ref'][0],photo.height/spec['ref'][1]
        allowed=binary_dilation(binary_fill_holes(guide),iterations=round(12*sx))
        selected=(pred>.5)&allowed
        if key=='curry':
            extra=Image.new('L',photo.size)
            ImageDraw.Draw(extra).polygon([(218,488),(250,489),(249,498),(246,508),(242,518),(213,519),(214,507),(216,496)],fill=255)
            selected |= np.asarray(extra)>0
        if key=='allen':
            # The separate ball needs its own selection; preserve the actual motion blur.
            ball=Image.new('L',photo.size)
            ImageDraw.Draw(ball).ellipse((round(589*sx),round(388*sy),round(692*sx),round(493*sy)),fill=255)
            y0,y1=round(370*sy),round(498*sy)
            selected[y0:y1] = np.asarray(ball)[y0:y1]>127
        for box,points in clips.get(key,[]):
            selection=Image.new('L',photo.size)
            ImageDraw.Draw(selection).polygon([(round(x*sx),round(y*sy)) for x,y in points],fill=255)
            x0,y0,x1,y1=[round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box)]
            selected[y0:y1,x0:x1]=np.asarray(selection)[y0:y1,x0:x1]>127
        for points in erase.get(key,[]):
            exclusion=Image.new('L',photo.size)
            ImageDraw.Draw(exclusion).polygon([(round(x*sx),round(y*sy)) for x,y in points],fill=255)
            selected[np.asarray(exclusion)>0]=False
        # Small matte band aligns the selection with actual photo color boundaries.
        radius=max(1,round(sx))
        trimap=np.full(guide.shape,.5)
        trimap[~binary_dilation(selected,iterations=radius)]=0
        trimap[binary_erosion(selected,iterations=radius)]=1
        pixels=np.asarray(photo)/255.
        alpha=estimate_alpha_cf(pixels,trimap)
        alpha[alpha<.02]=0
        alpha[alpha>.98]=1
        fg=estimate_foreground_ml(pixels,alpha)
        fg[alpha==1]=pixels[alpha==1]
        fg[alpha==0]=0
        result=Image.fromarray(np.uint8(np.clip(np.dstack([fg,alpha])*255,0,255)))
        result.save(WORK/f'{key}-refined-cutout.png')
        print(f'Finished {key}',flush=True)
    proof('refined-cutout');edge_proofs()


def publish():
    (ASSETS/'cutouts').mkdir(exist_ok=True)
    (ASSETS/'proofs').mkdir(exist_ok=True)
    for key in MASKS:
        shutil.copy2(WORK/f'{key}-refined-cutout.png',ASSETS/'cutouts'/f'{key}.png')
        shutil.copy2(WORK/f'{key}-edges.jpg',ASSETS/'proofs'/f'{key}-edges.jpg')
    summary=Image.new('RGB',(1120,612))
    with Image.open(WORK/'curry-edges.jpg') as curry:
        summary.paste(curry.crop((0,0,1120,306)),(0,0))
    with Image.open(WORK/'rodman-detroit-edges.jpg') as rodman:
        summary.paste(rodman.crop((0,612,1120,918)),(0,306))
    summary.save(ASSETS/'proofs'/'edge-comparison.jpg',quality=96)
    print('Published reviewed cutouts and edge proofs; run build_dot_press.py to export.')


def edge_proofs():
    areas={
        'curry':[(185,105,244,185),(245,135,307,240),(202,480,273,550),(205,610,298,690)],
        'rodman-detroit':[(600,33,712,156),(520,123,576,203),(386,425,477,533),(295,550,445,647)],
        'rodman-chicago':[(458,177,549,260),(376,343,473,398),(320,421,402,550),(555,385,635,509)],
        'allen':[(593,492,673,601),(722,523,816,634),(592,1190,666,1390),(515,1450,735,1610)],
    }
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    for key,spec in MASKS.items():
        photo=Image.open(ASSETS/'sources'/spec['file']).convert('RGB')
        old=photo.convert('RGBA');old.putalpha(coarse_mask(photo,spec).filter(ImageFilter.GaussianBlur(.55*photo.width/spec['ref'][0])))
        new=Image.open(WORK/f'{key}-refined-cutout.png')
        sheet=Image.new('RGB',(1120,4*306),'#dae0e3')
        for row,box in enumerate(areas[key]):
            sx,sy=photo.width/spec['ref'][0],photo.height/spec['ref'][1]
            box=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box))
            for col,(im,color,label) in enumerate([(photo,'#fff','Source'),(old,'#fff','Old mask'),(new,'#fff','Refined / white'),(new,'#101820','Refined / dark')]):
                crop=im.crop(box);ratio=min(270/crop.width,270/crop.height)
                crop=crop.resize((round(crop.width*ratio),round(crop.height*ratio)),Image.Resampling.NEAREST)
                panel=Image.new('RGB',(280,280),color)
                panel.paste(crop,((280-crop.width)//2,(280-crop.height)//2),crop if crop.mode=='RGBA' else None)
                sheet.paste(panel,(col*280,row*306+26))
                ImageDraw.Draw(sheet).text((col*280+8,row*306+4),label,fill='#24323d',font=font)
        sheet.save(WORK/f'{key}-edges.jpg',quality=96)


def source_details():
    regions={'curry':(195,475,308,540),'rodman-detroit':(620,380,720,580),'rodman-chicago':(330,370,430,465),'allen':(635,1470,730,1605)}
    for key,box in regions.items():
        spec=MASKS[key]
        photo=Image.open(ASSETS/'sources'/spec['file']).convert('RGB').resize(spec['ref'],Image.Resampling.LANCZOS)
        crop=photo.crop(box).resize(((box[2]-box[0])*3,(box[3]-box[1])*3))
        pen=ImageDraw.Draw(crop,'RGBA');font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
        for x in range((box[0]//10+1)*10,box[2],10):
            px=(x-box[0])*3
            pen.line((px,0,px,crop.height),fill=(0,220,200,75));pen.text((px+1,1),str(x),font=font,fill='cyan')
        for y in range((box[1]//10+1)*10,box[3],10):
            py=(y-box[1])*3
            pen.line((0,py,crop.width,py),fill=(0,220,200,75));pen.text((0,py+1),str(y),font=font,fill='cyan')
        crop.save(WORK/f'{key}-source-grid.jpg',quality=97)


if __name__=='__main__':
    WORK.mkdir(parents=True,exist_ok=True)
    before=WORK/'before'
    if not before.exists():
        before.mkdir()
        for file in (ASSETS/'exports').glob('*.png'):
            shutil.copy2(file,before/file.name)
    if '--finish' in sys.argv:
        finish()
    elif '--source-details' in sys.argv:
        source_details()
    elif '--publish' in sys.argv:
        publish()
    elif '--proof' in sys.argv:
        edge_proofs()
    else:
        segment()
