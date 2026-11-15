"""Local, narrated MP4 explainers derived only from the exported radar archive."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from src.common import ROOT

LOCK = threading.Lock()
CACHE = ROOT / 'outputs/echo-videos'
MANIFEST = ROOT / 'frontend/public/data/echo/manifest.json'
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'


def storyboard(data, region, index):
    row = region['series'][index]
    date = datetime.strptime(row['date'], '%Y%m%d').strftime('%d %B %Y')
    if row['valid_pixels'] <= 0 or row['water_km2'] is None:
        raise ValueError('This observation has no usable measurement to explain.')
    scenes = [dict(title='A place. A date. An observation.', kind='map', frames=[index],
        text=f"This is {region['name']}, in the Lake Inba study area, Japan. On {date}, radar-based predictions mapped {row['water_km2']:.3f} square kilometres of water in the selected comparable area.")]
    if index:
        previous = region['series'][index-1]
        delta = row['water_km2'] - previous['water_km2']
        change = f"{'increased' if delta > 0 else 'decreased'} by {abs(delta):.3f} square kilometres" if abs(delta) >= .0005 else 'stayed the same to three decimal places'
        scenes.append(dict(title='What changed since the previous pass?', kind='compare', frames=[index-1,index],
            text=f"Compare the previous observation on {datetime.strptime(previous['date'],'%Y%m%d').strftime('%d %B')} with {date}. Total predicted water {change}. The gap is {data['observations'][index]['gap_days']} days; we cannot see what happened between passes."))
    else:
        scenes.append(dict(title='The beginning of the record', kind='map', frames=[index],text='This is the first observation in this archive. There is no earlier observation here to establish a change. No previous measurement does not mean that the area was dry.'))
    scenes.append(dict(title='Follow the full timeline',kind='chart',frames=[index],
        text=f"The timeline contains {len(region['series'])} real observations. The highlighted date has water on approximately {round(row['water_fraction']*100)} percent of the selected comparable area. Each dot is an observation; spacing on this chart follows the actual dates."))
    if region['id'] != 'study':
        scenes.append(dict(title='The change a before-and-after can hide',kind='compare',frames=[0,len(region['series'])-1],text='This patch is classified as non-water at the first and last observations, but as water on intermediate dates. Looking only at the endpoints would miss that change. This does not establish its cause.'))
    scenes.append(dict(title='What the evidence can tell us',kind='coverage',frames=[index],text=f"These statistics compare only pixels available on every date, covering {data['common_coverage_percent']} percent of the full study area. The classifications are exploratory radar-based predictions, not confirmed floods. Grey is radar context, teal is predicted water, and purple marks temporary-water candidates."))
    return scenes


def font(size):
    return ImageFont.truetype(FONT,size)


def wrapped(draw, text, xy, width, size=23, color='#e0e9ef', line_height=32):
    x,y=xy; line=''
    for word in text.split():
        candidate=f'{line} {word}'.strip()
        if draw.textlength(candidate,font=font(size))>width and line:
            draw.text((x,y),line,font=font(size),fill=color);y+=line_height;line=word
        else:line=candidate
    draw.text((x,y),line,font=font(size),fill=color)


def scene_image(data,region,index,scene,target):
    image=Image.new('RGB',(1280,720),'#0a1420');draw=ImageDraw.Draw(image)
    draw.text((36,24),'SARScope / EARTH ECHO / NARRATED EXPLAINER',font=font(17),fill='#9bdfcb')
    draw.text((36,62),scene['title'],font=font(32),fill='#f0f5f4')
    draw.text((36,107),region['name'],font=font(18),fill='#bac9d4')
    def raster(i,box):
        source=ROOT/'frontend/public'/data['observations'][i]['image'].lstrip('/')
        with Image.open(source) as raw:
            crop=raw.crop(tuple(region['box']));scale=min((box[2]-box[0])/crop.width,(box[3]-box[1])/crop.height);crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.NEAREST)
            image.paste(crop,(box[0]+(box[2]-box[0]-crop.width)//2,box[1]+(box[3]-box[1]-crop.height)//2))
        draw.text((box[0]+12,box[3]+7),datetime.strptime(data['observations'][i]['date'],'%Y%m%d').strftime('%d %b %Y'),font=font(19),fill='#cae4de')
    if scene['kind']=='compare':
        raster(scene['frames'][0],(35,150,620,485));raster(scene['frames'][1],(655,150,1240,485))
        draw.line((640,150,640,505),fill='#45606d',width=2)
    elif scene['kind']=='chart':
        values=region['series'];dates=[datetime.strptime(r['date'],'%Y%m%d') for r in values];span=(dates[-1]-dates[0]).days or 1;maximum=max(r['water_km2'] for r in values) or 1
        points=[(70+(d-dates[0]).days/span*1130,460-r['water_km2']/maximum*250) for d,r in zip(dates,values)]
        draw.line((70,180,70,460,1200,460),fill='#566977',width=2);draw.line(points,fill='#81dfc8',width=4)
        for i,(x,y) in enumerate(points):
            radius=9 if i==index else 5;draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill='#d6b0ff' if i==index else '#81dfc8')
        draw.text((75,155),f'Predicted water · 0–{maximum:.3f} km²',font=font(21),fill='#cfe2e4')
        draw.text((70,480),dates[0].strftime('%d %b %Y'),font=font(19),fill='#bcced7');draw.text((1030,480),dates[-1].strftime('%d %b %Y'),font=font(19),fill='#bcced7')
    else:
        raster(index,(40,150,640,485));row=region['series'][index]
        headline=f"{data['common_coverage_percent']}%" if scene['kind']=='coverage' else f"{row['water_km2']:.3f} km²"
        draw.text((710,210),headline,font=font(52),fill='#9ce3cd')
        wrapped(draw,'of the full study area is comparable on every date' if scene['kind']=='coverage' else 'predicted water on common valid pixels',(710,285),490)
        wrapped(draw,'Teal: predicted water. Purple: temporary-water candidate. Grey: radar context. Dark: no data.',(710,380),480,18,line_height=26)
    draw.rectangle((20,535,1260,690),fill='#172739')
    wrapped(draw,scene['text'],(38,552),1200,22,line_height=30)
    draw.text((36,697),'Actual observations • Generated narration • Exploratory predictions, not a flood warning',font=font(13),fill='#93aab6')
    image.save(target)


def command(args, timeout=90):
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=timeout)


def create_video(region_id,date):
    data=json.loads(MANIFEST.read_text())
    region=next((r for r in data['regions'] if r['id']==region_id),None)
    index=next((i for i,o in enumerate(data['observations']) if o['date']==date),None)
    if region is None or index is None:raise ValueError('Choose an available Earth Echo region and observation.')
    scenes=storyboard(data,region,index)
    fingerprint=hashlib.sha256(MANIFEST.read_bytes()+Path(__file__).read_bytes()+json.dumps([region_id,date]).encode()).hexdigest()[:24]
    CACHE.mkdir(parents=True,exist_ok=True);target=CACHE/f'{fingerprint}.mp4'
    if target.is_file():return target
    if not shutil.which('say') or not shutil.which('ffmpeg') or not shutil.which('ffprobe') or not Path(FONT).is_file():
        raise RuntimeError('Video narration requires the local Mac voice service and FFmpeg. Start the project on the configured Mac to generate this video.')
    if not LOCK.acquire(blocking=False):raise RuntimeError('Another explainer is being rendered. Please try again shortly.')
    try:
        if target.is_file():return target
        with tempfile.TemporaryDirectory(prefix='echo-video-') as tmp:
            folder=Path(tmp)
            for i,scene in enumerate(scenes):
                png=folder/f'{i}.png';audio=folder/f'{i}.aiff';clip=folder/f'{i}.mp4';script=folder/f'{i}.txt';script.write_text(scene['text'])
                scene_image(data,region,index,scene,png)
                command(['say','-v','Rishi','-r','165','-f',str(script),'-o',str(audio)])
                probe=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(audio)],timeout=15).decode().strip()
                try:duration=float(probe)
                except ValueError:raise RuntimeError('The local voice service could not generate audio. Restart the backend with access to the Mac voice service.') from None
                if not 0<duration<90:raise RuntimeError('Narration duration is invalid; video generation stopped.')
                command(['ffmpeg','-y','-loglevel','error','-loop','1','-framerate','24','-i',str(png),'-i',str(audio),'-t',str(duration),'-vf','fade=t=in:st=0:d=0.25','-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-shortest',str(clip)])
            listing=folder/'clips.txt';listing.write_text('\n'.join(f"file '{i}.mp4'" for i in range(len(scenes))))
            output=folder/'finished.mp4';command(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(output)])
            staged=CACHE/f'.{fingerprint}.tmp';shutil.copyfile(output,staged);staged.replace(target)
        return target
    finally:LOCK.release()
