#!/usr/bin/env python
# encoding: utf-8
'''
check_kdenlive -- shortdesc

check_kdenlive is a description

It defines classes_and_methods

@author:     Piotr Nikiel (based on kdenparse)

@copyright:  2014 organization_name. All rights reserved.

@license:    license

@contact:    user_email
@deffield    updated: Updated
'''

import sys
import os
import re
import traceback
import uuid

from optparse import OptionParser
from kdenparse import KdenParse
from  xml.dom.minidom import Element,Text,Document

media_folder="__media__"


def create_simple_element(name,value):
    d=Document()
    
    e=Element(name)
    e.appendChild(d.createTextNode(value))
    return e
    
def get_first_value(n):
    return n.firstChild.data

def create_rate():
    e=Element("rate")
    e.appendChild(create_simple_element("ntsc", "FALSE"))
    e.appendChild(create_simple_element("timebase", "25"))
    return e

def get_property(properties,name):
    for p in properties:
        if p.getAttribute("name")==name:
            return get_first_value(p)
    return None

def producer_get_audio_channels_from_properties(properties):
    audio_index = get_property(properties, "audio_index")
    print "audio_index="+str(audio_index)
    if int(audio_index) < 0:
        #  as experienced, this is still possible that audio stream exists ...
        for i in range(0,2):
            stream_type=get_property(properties, "meta.media."+str(i)+".stream.type")
            if stream_type!=None and stream_type=="audio":
                num_ch = get_property(properties, "meta.media."+str(i)+".codec.channels")
                return num_ch
        return 0
    else:
        return get_property(properties, "meta.media."+str(audio_index)+".codec.channels")

def get_audio_params_from_properties(properties):
    """ returns [sample_rate, depth] """
    sample_rate=-1
    depth=-1
    for i in range(0,2):
        stream_type=get_property(properties, "meta.media."+str(i)+".stream.type")
        if stream_type!=None and stream_type=="audio":
            sample_rate = get_property(properties, "meta.media."+str(i)+".codec.sample_rate")
            depth=16
    return [sample_rate, depth]

used_files={}

def get_file_entry(resource,clip_len,properties):
    resource_base_name = str(os.path.basename(resource))
    fn = resource_base_name.split(".")[0]
    o_file = Element("file")
    o_file.setAttribute("id", fn)
    if not used_files.has_key(resource_base_name):
        used_files[resource_base_name]=resource
        # here add info of file
        #     o_file.appendChild(create_simple_element("name", clip_resource_basename))
        o_file.appendChild(create_simple_element("name", resource_base_name))
        o_pathurl=create_simple_element("pathurl", resource)
        o_file.appendChild(o_pathurl)
        o_rate=Element("rate")
        o_rate.appendChild(create_simple_element("timebase", "25"))
        o_file.appendChild(o_rate)
        o_file.appendChild(create_simple_element("duration", str(clip_len)))
        o_file_media = Element("media")
        video_index=get_property(properties, "video_index")
        if int(video_index)>=0:
            o_file_media_video = Element("video")
            o_file_media_video.appendChild(create_simple_element("duration", str(clip_len)))
            o_file_media.appendChild(o_file_media_video)
        num_audio_channels=producer_get_audio_channels_from_properties(properties)
        if int(num_audio_channels)>0:
            o_file_media_audio = Element("audio")
            [sample_rate, depth] = get_audio_params_from_properties(properties)
            o_samplecharacteristics = Element("samplecharacteristics")
            o_samplecharacteristics.appendChild(create_simple_element("samplerate", str(sample_rate)))
            o_samplecharacteristics.appendChild(create_simple_element("depth", str(depth)))
            o_file_media_audio.appendChild(o_samplecharacteristics)
            o_file_media_audio_channelcount = create_simple_element("channelcount", num_audio_channels)
            o_file_media_audio.appendChild(o_file_media_audio_channelcount)
            o_file_media.appendChild(o_file_media_audio)
        o_file.appendChild(o_file_media)
    return o_file

clip_id=0

def create_clipitem_from_playlist_entry(k,e,properties,e_in,e_out,playlist_current_frame):
    global clip_id
    """ Creates clipitem element.
    The subelements common to both audio and video clipitem (that is : name, duration, rate, in, out, start, end) are included """
    e_len = e_out-e_in
    o_clipitem = Element("clipitem")
    resource = get_property(properties, "resource")
    print resource
    length = get_property(properties, "length")
    resource_base_name = str(os.path.basename(resource))
    o_clipitem.setAttribute("id", resource_base_name+"_"+str(clip_id))
    clip_id = clip_id+1
    print resource_base_name
    o_clipitem.appendChild(create_simple_element("name", resource_base_name))
    o_clipitem.appendChild(create_simple_element("duration", length))
    o_clipitem.appendChild(create_rate())
    o_clipitem.appendChild(create_simple_element("in", str(e_in)))
    o_clipitem.appendChild(create_simple_element("out", str(e_out)))
    o_clipitem.appendChild(create_simple_element("start", str(playlist_current_frame)))
    o_clipitem.appendChild(create_simple_element("end", str(playlist_current_frame+e_len)))

    return o_clipitem  
                    
def parse_playlist_entry(k,e, playlist_current_frame):
    """ For each entry analyzes its producer and spits out:
        - a list of video clips obtained from parsing the entry
        - a 2 lists of audio clips obrained from parsing the entry 
    """
    video_clips=[]
    audio_clips=[[],[]]
    e_in = int(e.getAttribute("in"))
    e_out = int(e.getAttribute("out"))
    e_p = e.getAttribute("producer")
    clip = k.getGivenProducer(e_p)
    properties = clip.getElementsByTagName("property")
    # check service 
    mlt_service=get_property(properties, "mlt_service")
    if mlt_service!="avformat":
        print "----------------------"
        print "Service different from avformat: not supported yet! do it manually"
        print "For resource given by producer:: "+str(e_p)
        print "----------------------"
        return [[],[[],[]]]
    print "producer for this entry found"
    clip_len = get_property(properties, "length")
    audio_stream_index = get_property(properties, "audio_index")
    video_stream_index = get_property(properties, "video_index")
    if video_stream_index==None:
        video_stream_index=-1
    if audio_stream_index==None:
        audio_stream_index=-1
    if video_stream_index<0 and audio_stream_index<0:
        print "----------------------------------------------------------"
        print "Bizarre case: looks like clip with neither audio nor video"
        print "For resource: "+get_property(properties, "resource")
        print "----------------------------------------------------------"
    print "video_stream_index="+str(video_stream_index)+" audio_stream_index="+str(audio_stream_index)
    generated_clips=[]
    if int(video_stream_index)>=0:
        video_clip = create_clipitem_from_playlist_entry(k, e, properties, e_in, e_out, playlist_current_frame)
        video_clip.appendChild(get_file_entry(get_property(properties, "resource"), clip_len, properties))
        o_sourcetrack=Element("sourcetrack")
        o_sourcetrack.appendChild(create_simple_element("mediatype", "video"))
        video_clip.appendChild(o_sourcetrack)
        video_clips.append(video_clip)
        clip_dict={'clip':video_clip, 'mediatype':"video"}
        generated_clips.append(clip_dict)
    if int(audio_stream_index)>=0:
        num_audio_channels=get_property(properties, "meta.media."+str(audio_stream_index)+".codec.channels")
        # if we have one channel (mono) it should be added to both tracks
        for audio_ch in range(0,2):
            audio_clip = create_clipitem_from_playlist_entry(k, e, properties, e_in-3, e_out-3, playlist_current_frame)
            audio_clip.appendChild(get_file_entry(get_property(properties, "resource"), clip_len, properties))
            o_sourcetrack=Element("sourcetrack")
            o_sourcetrack.appendChild(create_simple_element("mediatype", "audio"))
            if int(num_audio_channels)>1:
                o_sourcetrack.appendChild(create_simple_element("trackindex", str(audio_ch+1)))
            else:
                o_sourcetrack.appendChild(create_simple_element("trackindex", "1"))  # mono track
            audio_clip.appendChild(o_sourcetrack)
            audio_clips[audio_ch].append(audio_clip)
            clip_dict={'clip':audio_clip, 'mediatype':"audio"}
            generated_clips.append(clip_dict)
    # now establish links between the clips
    for clip in generated_clips:
        for linked_clip in generated_clips:
            o_link=Element("link")
            #import pdb; pdb.set_trace()
            o_link.appendChild(create_simple_element("linkclipref", linked_clip['clip'].getAttribute("id")))
            o_link.appendChild(create_simple_element("mediatype", linked_clip['mediatype']))
            o_link.appendChild(create_simple_element("clipindex", "1"))
            if linked_clip['mediatype']=="audio":
                o_link.appendChild(create_simple_element("groupindex", "1"))
            clip['clip'].appendChild(o_link)
    return [video_clips,audio_clips]   

                
def parse_playlist(k,playlist):
    """ Goes through all entries of a playlist
    Returns video_track and audio_track corresponding to the playlist
    """
    fcp_video_track=Element("track")  # should contain clipitems for video
    fcp_audio_tracks=[Element("track"),Element("track")]  # should contain clipitems for audio
    for ch in range(0,2):
        fcp_audio_tracks[ch].appendChild(create_simple_element("outputchannelindex", str(ch+1)))
    entries=playlist.childNodes
    playlist_current_frame = 0
    print entries
    for e in entries:
        if e.nodeType!=e.ELEMENT_NODE:
            continue
        tagName=e.tagName
        if tagName=="blank":
            blank_len=e.getAttribute("length")
            playlist_current_frame = playlist_current_frame + int(blank_len)
            continue
        else:
            # okay so this is regular entry
            [video_clips,audio_clips]=parse_playlist_entry(k,e,playlist_current_frame)
            for video_clip in video_clips:
                fcp_video_track.appendChild(video_clip)
            for ch in range(0,2):
                for audio_clip in audio_clips[ch]:
                    fcp_audio_tracks[ch].appendChild(audio_clip)
            e_in = int(e.getAttribute("in"))
            e_out = int(e.getAttribute("out"))
            e_len=e_out-e_in
            playlist_current_frame = playlist_current_frame + e_len
         
    fcp_video_track.appendChild(create_simple_element("enabled", "TRUE") )
    fcp_video_track.appendChild(create_simple_element("locked", "FALSE") )
    for ch in range(0,2):
        fcp_audio_tracks[ch].appendChild(create_simple_element("enabled", "TRUE") )
        fcp_audio_tracks[ch].appendChild(create_simple_element("locked", "FALSE") )                              
    return [fcp_video_track,fcp_audio_tracks]    
    
def check(fname):
    k = KdenParse(fname)
    
    
    #tutaj utworz sekwencje
    o_sequence = Element("sequence");
    o_sequence.setAttribute("id", "seq_kdenlive");
    o_sequence.appendChild(create_simple_element("uuid", str(uuid.uuid4()).upper()))
    o_sequence.appendChild(create_simple_element("name", "seq_kdenlive"))
    o_sequence.appendChild(create_simple_element("duration", "0"))
    # TODO add duration
    o_sequence.appendChild(create_rate())
    o_timecode = Element("timecode")
    o_timecode.appendChild(create_rate())
    o_timecode.appendChild(create_simple_element("string", "01:00:00:00"))
    o_timecode.appendChild(create_simple_element("frame", "90000"))
    o_timecode.appendChild(create_simple_element("source", "source"))
    o_timecode.appendChild(create_simple_element("displayformat", "NDF"))
    o_sequence.appendChild(o_timecode)
    o_media = Element ("media");
    o_video = Element ("video");
    o_audio = Element ("audio")
    o_format = Element ("format")
    o_samplecharacteristics = Element("samplecharacteristics")
    o_samplecharacteristics.appendChild(create_simple_element("width","1920"))
    o_samplecharacteristics.appendChild(create_simple_element("height","1080"))
    o_samplecharacteristics.appendChild(create_simple_element("anamorphic","FALSE"))
    o_samplecharacteristics.appendChild(create_simple_element("pixelaspectratio","Square"))
    o_samplecharacteristics.appendChild(create_simple_element("fielddominance","upper"))
    o_samplecharacteristics.appendChild(create_rate())
    o_samplecharacteristics.appendChild(create_simple_element("colordepth", "24"))
    o_codec=Element("codec")
    o_codec.appendChild(create_simple_element("name", "AVID DNxHD Codec"))
    o_samplecharacteristics.appendChild(o_codec)
    o_format.appendChild(o_samplecharacteristics)
    o_video.appendChild(o_format)
    
    fcp_video_tracks=[]
    fcp_audio_tracks=[]
    
    maintractor = k.getMainTractor()
    print "maintractor found"
    # now find for video tracks
    tracks=maintractor.getElementsByTagName("track")
    videoTrackId=0
    audioTrackId=0
    audio_tracks_for_later=[]
    for t in tracks:
        if t.getAttribute("hide")=="video":
            # this is audio track
            print "skipping 'hide' track - will do later"
            audio_tracks_for_later.append(t)
        else:
            # skip black_track
            producer=t.getAttribute("producer")
            if producer=="black_track":
                print "skipping black track"
            else:
                # measn this is video track
                videoTrackId=videoTrackId+1
                
            
                print "not a black track"
                print "TRACK: Video"+str(videoTrackId)
                # lets look for playlist of such name
                playlist=k.getGivenPlaylist(producer)

                [fcp_video_track, fcp_audio_track] = parse_playlist(k, playlist)
                if fcp_video_track!=None:
                    o_video.appendChild(fcp_video_track)
                for track in range(0,2):
                    o_audio.appendChild(fcp_audio_track[track])
    for t in audio_tracks_for_later:
        print 'doing audio track postponed'
        producer=t.getAttribute("producer")
        # lets look for playlist of such name
        playlist=k.getGivenPlaylist(producer)

        [fcp_video_track, fcp_audio_track] = parse_playlist(k, playlist)
        print "after parsing returned video_track="+str(fcp_video_track)+" audio_track="+str(fcp_audio_track)
        for ch in range(0,2):
            o_audio.appendChild(fcp_audio_track[ch])
                
                
#                 entries=playlist.childNodes
#                 print entries
#                 for e in entries:
#                     if e.nodeType!=e.ELEMENT_NODE:
#                         continue
#                     tagName=e.tagName
#                     if tagName=="blank":
#                         blank_len=e.getAttribute("length")
#                         playlist_current_frame = playlist_current_frame + int(blank_len)
#                         continue
#                     else:
#                         e_in = int(e.getAttribute("in"))
#                         e_out = int(e.getAttribute("out"))
#                         e_len=e_out-e_in
#                         e_p = e.getAttribute("producer")
#                         clip = k.getGivenProducer(e_p)
#                         print "producer for this entry found"
#                         properties = clip.getElementsByTagName("property")
#                         clip_resource=""
#                         clip_len="1"
#                         for my_prop in properties:
#                             n=my_prop.getAttribute("name")
#                             if n=="resource":
#                                 clip_resource=get_first_value(my_prop)
#                             if n=="length":
#                                 clip_len=get_first_value(my_prop)
#                         clip_resource_basename=os.path.basename(clip_resource)
#                         
#                         o_clipitem = Element("clipitem")
#                         o_clipitem.appendChild(create_simple_element("name", clip_resource_basename))
#                         o_clipitem.appendChild(create_simple_element("duration", str(e_len)))
#                         o_clipitem.appendChild(create_rate())
#                         o_clipitem.appendChild(create_simple_element("start", str(playlist_current_frame)))
#                         o_clipitem.appendChild(create_simple_element("end", str(playlist_current_frame+e_len)))
#                         o_clipitem.appendChild(create_simple_element("in", str(e_in)))
#                         o_clipitem.appendChild(create_simple_element("out", str(e_out)))
#                         
#                         o_file = Element("file")
#                         o_file.appendChild(create_simple_element("name", clip_resource_basename))
#                         o_pathurl=create_simple_element("pathurl", clip_resource)
#                         o_file.appendChild(o_pathurl)
#                         o_file.appendChild(create_simple_element("duration", clip_len))
#                         o_file_media = Element("media")
#                         o_file_media_video = Element("video")
#                         o_file_media_video.appendChild(create_simple_element("duration", clip_len))
#                         o_file_media_audio = Element("audio")
#                         o_file_media_audio_channelcount = create_simple_element("channelcount", producer_get_audio_channels_from_properties(properties))
#                         o_file_media_audio.appendChild(o_file_media_audio_channelcount)
#                         o_file_media.appendChild(o_file_media_video)
#                         o_file_media.appendChild(o_file_media_audio)
#                         o_file.appendChild(o_file_media)
# 
#                         o_clipitem.appendChild(o_file)
#                         o_sourcetrack = Element("sourcetrack")
#                         o_sourcetrack.appendChild(create_simple_element("mediatype", "video"))
#                         o_clipitem.appendChild(o_sourcetrack)
#                         o_track.appendChild(o_clipitem)
#                         playlist_current_frame = playlist_current_frame+e_len
#                 o_track.appendChild(create_simple_element("enabled", "TRUE"))
#                 o_track.appendChild(create_simple_element("locked", "FALSE"))
#                 o_video.appendChild(o_track)
    o_media.appendChild(o_video)
    o_media.appendChild(o_audio)
    o_sequence.appendChild(o_media)
    #print o_sequence.toprettyxml("  ")
    o_xmeml=Element("xmeml")
    o_xmeml.setAttribute("version", "5")
    o_sequence.appendChild(create_simple_element("ismasterclip", "FALSE"))
    o_xmeml.appendChild(o_sequence)
    f=file('fcp.xml','w')
    o_xmeml.writexml(f,"","  ","\n")
    
    
    
        
def main(argv=None):
    '''Command line options.'''

    fn=argv[1]
    try:
        # MAIN BODY #
        print "Infile="+fn
        check(fn)
        

    except Exception, e:
        print str(e)
        traceback.print_exc()
        return 2



sys.exit(main(sys.argv))
