"""Reproducible photographic cutouts and halftone review assets. No generated pixels."""
from pathlib import Path
import math
import json
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'src/nba_gm_data/gui/assets/dot-press'
OUT = ASSETS / 'exports'
SIZE = 1024

# Legacy selections now define framing only, never the exported photographic edges.
# Refined, source-resolution RGBA cutouts live in assets/dot-press/cutouts/.
MASKS = {
    'curry': {
        'file': 'curry-finals.jpg', 'ref': (493, 740),
        'polygons': [
            [(209,117),(215,121),(214,133),(217,138),(218,118),(222,117),(224,136),(226,122),(230,122),(232,137),(231,148),(227,156),(231,181),(232,207),(235,234),(240,261),(247,274),(251,270),(251,252),(258,240),(266,235),(278,235),(282,246),(285,257),(287,266),(291,271),(289,245),(282,223),(270,189),(266,180),(266,168),(269,156),(270,149),(274,150),(274,162),(277,144),(281,144),(281,162),(282,151),(285,153),(283,169),(280,181),(292,208),(300,232),(310,258),(315,280),(316,292),(311,307),(307,321),(302,339),(300,359),(296,380),(297,390),(303,412),(305,441),(303,471),(307,483),(297,489),(297,509),(295,536),(294,561),(291,584),(290,609),(286,624),(283,638),(283,653),(290,668),(290,676),(280,681),(266,676),(257,670),(254,661),(255,647),(261,624),(266,614),(266,595),(262,568),(259,541),(257,518),(255,505),(251,501),(248,519),(244,550),(238,583),(237,607),(239,626),(245,649),(254,662),(254,668),(241,672),(228,670),(220,665),(214,652),(211,637),(211,622),(214,604),(214,589),(213,565),(215,541),(218,520),(221,505),(220,490),(208,488),(208,467),(211,434),(212,414),(215,397),(215,387),(216,372),(216,351),(220,332),(220,314),(220,301),(216,287),(212,269),(211,249),(212,225),(212,201),(212,177),(213,159),(208,144),(204,131),(205,124),(208,126),(213,137)],
            [(219,59),(229,61),(239,67),(245,78),(248,91),(246,103),(239,112),(228,118),(215,117),(205,113),(197,104),(193,94),(192,83),(196,72),(205,63)],
        ],
        'holes': [[(240,263),(240,246),(235,216),(231,185),(231,171),(250,205),(267,226),(282,240),(278,234),(265,232),(254,239),(248,251),(247,264)]],
    },
    'rodman-detroit': {
        'file': 'rodman-detroit.jpg', 'ref': (1100,735),
        'polygons': [[(482,58),(497,51),(514,49),(535,50),(551,57),(563,68),(570,80),(575,103),(582,117),(595,117),(610,111),(620,94),(621,76),(627,58),(642,44),(659,40),(678,43),(690,50),(694,62),(691,76),(687,84),(688,93),(679,101),(674,114),(668,123),(680,130),(695,139),(702,151),(701,169),(691,188),(684,205),(679,226),(676,245),(672,261),(668,275),(676,285),(679,306),(682,329),(693,348),(704,372),(710,397),(709,423),(704,445),(694,466),(689,477),(691,490),(699,510),(700,537),(693,559),(686,570),(678,574),(668,569),(660,555),(653,534),(650,516),(650,495),(654,475),(657,462),(654,451),(643,435),(632,413),(621,386),(608,367),(590,359),(571,374),(544,389),(509,406),(478,426),(462,436),(458,451),(452,475),(443,498),(437,516),(436,539),(430,554),(427,569),(430,588),(431,608),(435,621),(432,634),(416,639),(390,635),(370,633),(350,628),(329,619),(314,609),(304,596),(304,589),(313,584),(327,578),(347,570),(368,562),(378,548),(384,531),(391,512),(398,491),(405,466),(412,442),(421,414),(436,390),(458,368),(481,348),(506,334),(522,327),(529,310),(540,293),(546,280),(548,263),(551,245),(550,221),(549,199),(538,201),(522,210),(506,211),(496,202),(492,185),(491,162),(491,143),(491,134),(482,126),(477,117),(474,101),(474,87),(479,74)]],
        'holes': [[(526,161),(531,149),(541,141),(550,143),(562,158),(558,177),(550,187),(540,188),(532,183)]],
    },
    'rodman-chicago': {
        'file':'rodman-white.png','ref':(720,720),
        'polygons': [[(476,199),(485,191),(498,186),(512,186),(522,191),(529,200),(531,214),(527,228),(520,242),(517,246),(530,247),(542,254),(550,266),(554,284),(556,301),(554,326),(551,346),(546,363),(538,374),(530,380),(540,385),(552,387),(563,395),(575,413),(580,432),(586,435),(594,416),(603,400),(610,395),(617,396),(622,405),(625,418),(624,435),(620,454),(614,473),(605,489),(596,499),(583,502),(574,498),(568,490),(565,477),(565,462),(558,459),(551,455),(540,451),(527,447),(512,443),(493,440),(479,440),(460,445),(443,447),(421,444),(405,442),(389,441),(375,444),(370,452),(370,468),(374,489),(376,513),(375,532),(375,547),(381,556),(378,568),(369,575),(349,578),(328,576),(311,570),(301,562),(296,553),(300,548),(310,549),(321,546),(330,544),(335,535),(338,516),(338,495),(338,478),(337,464),(332,448),(332,431),(334,416),(343,402),(359,395),(380,390),(403,388),(425,385),(444,384),(455,373),(458,364),(458,358),(445,355),(432,354),(419,354),(406,352),(391,347),(382,337),(378,324),(379,312),(378,304),(380,298),(379,294),(384,292),(387,296),(389,290),(396,282),(406,284),(414,280),(425,269),(435,248),(446,239),(459,235),(471,226),(472,218),(470,214),(474,209)]],
        'holes': [],
    },
    'allen': {
        'file':'allen.jpg','ref':(1280,1921),
        'polygons': [[(615,503),(624,501),(628,509),(631,502),(638,502),(641,515),(648,516),(653,527),(656,540),(653,559),(644,576),(638,597),(632,625),(625,651),(620,679),(614,702),(629,701),(644,705),(658,716),(669,730),(675,747),(671,768),(661,782),(679,797),(690,808),(701,780),(716,757),(726,739),(732,715),(735,687),(737,659),(738,626),(736,613),(730,599),(730,579),(726,568),(728,560),(735,558),(744,570),(751,553),(765,540),(775,533),(780,534),(781,539),(770,550),(776,548),(791,536),(797,538),(797,544),(780,560),(800,551),(805,553),(806,560),(783,578),(801,570),(807,572),(807,578),(785,597),(774,607),(765,616),(767,641),(770,671),(776,704),(775,728),(774,745),(767,769),(758,790),(753,810),(741,834),(728,860),(723,888),(722,922),(715,954),(707,988),(697,1019),(705,1041),(712,1068),(716,1103),(719,1143),(720,1182),(711,1222),(710,1263),(709,1300),(709,1340),(711,1377),(711,1413),(713,1442),(720,1474),(710,1489),(705,1505),(711,1525),(715,1547),(721,1565),(723,1586),(715,1597),(696,1597),(681,1590),(666,1575),(657,1558),(648,1546),(642,1533),(648,1518),(656,1501),(654,1498),(637,1496),(627,1487),(628,1470),(633,1440),(636,1406),(640,1372),(643,1338),(642,1302),(638,1270),(638,1240),(631,1214),(623,1226),(614,1257),(605,1283),(594,1305),(589,1339),(583,1370),(581,1403),(580,1436),(580,1462),(589,1487),(589,1504),(583,1515),(586,1535),(595,1563),(596,1580),(587,1589),(568,1594),(555,1588),(545,1579),(540,1563),(536,1542),(533,1520),(530,1505),(529,1487),(529,1465),(530,1446),(527,1423),(525,1398),(525,1370),(527,1340),(532,1305),(535,1270),(527,1233),(524,1194),(525,1152),(528,1115),(533,1076),(545,1043),(552,1024),(552,1002),(552,970),(548,947),(545,923),(542,903),(544,879),(550,874),(553,853),(556,824),(562,791),(570,757),(578,723),(586,688),(594,655),(601,622),(608,590),(609,573),(605,555),(605,536),(609,520)]],
        'holes': [],
        # The moving ball is separated from the fingertips; preserve it as photographed.
        'ellipses': [(589,388,692,493)],
    },
}


def cutout(key, spec):
    photo = Image.open(ASSETS/'sources'/spec['file']).convert('RGB')
    sx, sy = photo.width/spec['ref'][0], photo.height/spec['ref'][1]
    mask = Image.new('L', photo.size)
    pen = ImageDraw.Draw(mask)
    for poly in spec['polygons']:
        pen.polygon([(round(x*sx),round(y*sy)) for x,y in poly], fill=255)
    for bounds in spec.get('ellipses', []):
        pen.ellipse(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(bounds)), fill=255)
    for poly in spec['holes']:
        pen.polygon([(round(x*sx),round(y*sy)) for x,y in poly], fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(.55*max(sx,sy)))
    framing = mask.getbbox()
    refined_path = ASSETS/'cutouts'/f'{key}.png'
    if not refined_path.exists():
        raise FileNotFoundError(f'Missing reviewed cutout: {refined_path}')
    refined = Image.open(refined_path)
    if refined.mode != 'RGBA' or refined.size != photo.size:
        raise ValueError(f'Cutout must be source-resolution RGBA: {refined_path}')
    photo = refined.crop(framing)
    target_height = {'curry':880,'allen':880,'rodman-detroit':776,'rodman-chicago':700}[key]
    fit = min(864/photo.width,target_height/photo.height)
    photo = photo.resize((round(photo.width*fit),round(photo.height*fit)),Image.Resampling.LANCZOS)
    normalized = Image.new('RGBA',(SIZE,SIZE))
    normalized.alpha_composite(photo,((SIZE-photo.width)//2,(SIZE-photo.height)//2))
    normalized.save(OUT/f'{key}-photo.png')
    return normalized


def press(photo, pitch, light_surface=True, tool=False, dot_scale=0.52):
    arr = np.asarray(photo)
    width, height = photo.size
    alpha = arr[:,:,3]/255.
    gray = np.asarray(photo.convert('L')).astype(float)/255.
    pixels = gray[alpha>.9]
    low,high = np.percentile(pixels,[2,98])
    tone = np.clip((gray-low)/max(.01,high-low),0,1)
    # Preserve the tonal image on both surfaces, including bright uniform outlines.
    density = .075 + .925*((1-tone) if light_surface and not tool else tone)**.84
    scale=3
    out=Image.new('RGBA',(width*scale,height*scale))
    pen=ImageDraw.Draw(out)
    color=(28,41,50,255) if light_surface else (228,237,240,255)
    for row,y in enumerate(np.arange(pitch/2,height,pitch)):
        for x in np.arange(pitch/2+(row%2)*pitch/2,width,pitch):
            ix,iy=int(x),int(y)
            if alpha[iy,ix]<.4:
                continue
            radius=pitch*dot_scale*math.sqrt(density[iy,ix])*alpha[iy,ix]
            ink=color
            if tool and arr[iy,ix,0]>int(arr[iy,ix,2])*1.4 and arr[iy,ix,0]>100:
                ink=(178,76,45,255) if light_surface else (243,148,97,255)
            pen.ellipse(((x-radius)*scale,(y-radius)*scale,(x+radius)*scale,(y+radius)*scale),fill=ink)
    out=out.resize((width,height),Image.Resampling.LANCZOS)
    # Clip dots to the photographic silhouette, especially fingertips and shoelaces.
    a=np.asarray(out.getchannel('A')).astype(float)*alpha
    out.putalpha(Image.fromarray(a.astype('uint8')))
    return out


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for key,spec in MASKS.items():
        photo=cutout(key,spec)
        for pitch,label in [(3.2,'fine'),(5.2,'press'),(8,'coarse')]:
            for light,name in [(True,'silver'),(False,'ink')]:
                press(photo,pitch,light).save(OUT/f'{key}-{label}-{name}.png')
        manifest.append({'id':key,'size':[SIZE,SIZE],'bounds':photo.getbbox()})
    for key in ['builder','finder']:
        photo=Image.open(ASSETS/'sources'/f'{key}.png').convert('RGBA')
        photo.save(OUT/f'{key}-photo.png')
        for pitch,label in [(3.2,'fine'),(5.2,'press'),(8,'coarse')]:
            for light,name in [(True,'silver'),(False,'ink')]:
                press(photo,pitch,light,tool=True).save(OUT/f'{key}-{label}-{name}.png')
        manifest.append({'id':key,'size':[SIZE,SIZE],'bounds':photo.getbbox()})
    (ASSETS/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    proof=Image.new('RGB',(1600,860),'#edf0f2')
    draw=ImageDraw.Draw(proof)
    for i,key in enumerate(MASKS):
        for j,suffix in enumerate(['photo','press-silver']):
            im=Image.open(OUT/f'{key}-{suffix}.png').resize((400,400),Image.Resampling.LANCZOS)
            proof.paste(im,(i*400,j*420),im)
        draw.text((i*400+20,824),key,fill='#1c2932')
    proof.save(ROOT/'artifacts/dot-press/photo-proof.jpg')
    with zipfile.ZipFile(ASSETS/'dot-press-review.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(OUT.glob('*.png')):
            archive.write(file,'exports/'+file.name)
        if (ASSETS/'ATTRIBUTION.md').exists():
            archive.write(ASSETS/'ATTRIBUTION.md','ATTRIBUTION.md')
    print(json.dumps(manifest))


if __name__=='__main__':
    main()
