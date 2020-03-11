# -*- coding: utf-8 -*-
#########################################################
# python
import os
import datetime
import traceback
import urllib
import time
from datetime import datetime
import re
import subprocess

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
import requests
from lxml import html
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError, APIC, TT2, TPE1, TRCK, TALB, USLT, error, TIT2
from mutagen.mp3 import EasyMP3 as MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
import mutagen
import platform




# sjva 공용
from framework import app, db, scheduler, path_app_root, celery
from framework.job import Job
from framework.util import Util


# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelItem

headers = {
    
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
    'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding' : 'gzip, deflate, br',
    'Accept-Language' : 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer' : ''
} 



#########################################################
class LogicNormal(object):
    session = requests.Session()
    driver = None
    
    @staticmethod
    @celery.task
    def scheduler_function():
        # 자동 추가 목록에 따라 큐에 집어넣음.
        try:
            logger.debug("음악정리 시작!")
            
            download_path = ModelSetting.get('download_path')
            organize_path = ModelSetting.get('proc_path')
            interval = ModelSetting.get('interval')
            emptyFolderDelete = ModelSetting.get('emptyFolderDelete')
            
            #LogicNormal.debugTest()
            #return
            dirList = []
            fileList = []
            
            for dir_path, dir_names, file_names in os.walk(download_path):
                rootpath = os.path.join(os.path.abspath(download_path), dir_path)
                
                if os.path.isdir(dir_path):
                    dirList.append(dir_path)

                for file in file_names:

                    try:
                        filepath = os.path.join(rootpath, file)
                        LogicNormal.mp3FileProc(filepath)
                        time.sleep(int(interval))
                    except Exception as e:
                        try:
                            logger.debug('Exception:%s', e)
                            logger.debug(traceback.format_exc())
                            newFolderPath = os.path.join(ModelSetting.get('err_path'), "ERR")
                            newFilePath = os.path.join(newFolderPath, os.path.basename(file))
                            realFilePath = LogicNormal.fileMove(os.path.join(rootpath, file) , newFolderPath, newFilePath)
                            LogicNormal.procSave("6" , "", "", "", "", "", "", "", realFilePath)
                            logger.debug('Exception:%s', e)
                            logger.debug(traceback.format_exc())
                        except Exception as e:
                            logger.debug('Exception:%s', e)
                            logger.debug(traceback.format_exc())

            if ModelSetting.get_bool('emptyFolderDelete'):
                for dir_path in dirList:
                    if download_path != dir_path and len(os.listdir(dir_path)) == 0:
                        os.rmdir(dir_path)

            logger.debug("===============END=================")
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def tagUpdate(req):

        id = ""
        title = ""
        artist = ""
        album = ""
        if 'id' in req.form:
            id = int(req.form['id'])
        if 'title' in req.form:
            title = str(req.form['title'])
        if 'artist' in req.form:
            artist = str(req.form['artist'])
        if 'album' in req.form:
            album = str(req.form['album'])
        
        logger.debug('id : ' + str(id))
        logger.debug('title : ' + str(title))
        logger.debug('artist : ' + str(artist))
        logger.debug('album : ' + str(album))
        
        
        entity = ModelItem.get(id)
        filePath = entity.filePath
        logger.debug("filePath : "  + filePath)
        if os.path.isfile(filePath):
            logger.debug("파일존재 확인"  + filePath)
            ext = filePath.split(".")[-1]
            if ext.upper() == "MP3":
                try:
                    tags = ID3(filePath)
                    tags.add(TALB(text=[unicode(str(album))]))
                    tags.add(TIT2(text=[unicode(str(title))]))
                    tags.add(TPE1(text=[unicode(str(artist))]))
                    tags.save()
                except ID3NoHeaderError:
                    logger.debug("MP3 except")
                    tags = ID3()
            if "M4A" == ext.upper() :
                
                tags = MP4(filePath)
                tags['\xa9nam'][0] = unicode(str(title))
                tags['\xa9ART'][0] = unicode(str(artist))
                tags['\xa9alb'][0] = unicode(str(album))
                tags.save()
                
                
            if "FLAC" == ext.upper() :

                tags = FLAC(filePath)
                tags['title'] = unicode(str(title))
                tags['artist'] = unicode(str(artist))
                tags['album'] = unicode(str(album))
                tags.save()
                
            logger.debug("파일처리시작"  + filePath)
            LogicNormal.mp3FileProc(filePath)

            ModelItem.delete(id)
            
            ret = {}
            return ret
        else:
            return      
        
        

    @staticmethod
    def get_html(url, referer=None, stream=False):
        try:
            data = ""

            if LogicNormal.session is None:
                LogicNormal.session = requests.session()
            #logger.debug('get_html :%s', url)
            headers['Referer'] = '' if referer is None else referer
            try:
                page_content = LogicNormal.session.get(url, headers=headers)
            except Exception as e:
                logger.debug("Connection aborted!!!!!!!!!!!")
                time.sleep(10) #Connection aborted 시 10초 대기 후 다시 시작
                page_content = LogicNormal.session.get(url, headers=headers)

            data = page_content.text
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return data
    
    @staticmethod
    def lcs(a, b):

        if len(a) == 0 or len(b) == 0:
            return 0
        if a == b :
            if len(a)<len(b):
                return len(b)
            else:
                return len(a)

        if len(a)<len(b):
            c = a
            a = b
            b = c
        prev = [0]*len(a)
        for i,r in enumerate(a):
            current = []
            for j,c in enumerate(b):
                if r==c:
                    e = prev[j-1]+1 if i* j > 0 else 1
                else:
                    e = max(prev[j] if i > 0 else 0, current[-1] if j > 0 else 0)
                current.append(e)
            prev = current
        
        return current[-1]
    
    @staticmethod
    def fileMove(originPath , newFolderPath, newFilePath):

        if not os.path.isdir(newFolderPath):
            logger.debug("폴더 생성 : " + newFolderPath)
            os.makedirs(newFolderPath)
        
        logger.debug("파일이동 시작")
        logger.debug(originPath + " ===>> " + newFilePath)
        if os.path.exists(newFilePath):
            os.remove(newFilePath)
        import shutil
        shutil.move(originPath, newFilePath)
        

        logger.debug("파일이동 완료")
        return newFilePath
    @staticmethod
    def procSave(statusCd , title, artist, album, titleByTag, artistByTag, albumByTag, searchKey, file):
        entity = {}
        entity['id'] = ""
        entity['statusCd'] = statusCd

        if statusCd == "1":
            entity['status'] = "정상"
        elif statusCd == "2":
            entity['status'] = "중복"
        elif statusCd == "3":
            entity['status'] = "매칭실패"
        elif statusCd == "4":
            entity['status'] = "태그정보없음"
        elif statusCd == "5":
            entity['status'] = "검색결과없음"
        elif statusCd == "6":
            entity['status'] = "오류"

        entity['title'] = title
        entity['artist'] = artist
        entity['album'] = album
        entity['titleByTag'] = titleByTag
        entity['artistByTag'] = artistByTag
        entity['albumByTag'] = albumByTag
        entity['searchKey'] = searchKey 
        entity['filePath'] = file
        ModelItem.save_as_dict(entity)
    
    @staticmethod
    def mp3FileProc(file):
        
        download_path = ModelSetting.get('download_path')
        organize_path = ModelSetting.get('proc_path')
        err_path = ModelSetting.get('err_path')
        maxCost = ModelSetting.get('maxCost')
        singleCost = ModelSetting.get('singleCost')
        
        notMp3delete = ModelSetting.get('notMp3delete')

        folderStructure = ModelSetting.get('folderStructure')
        fileRename = ModelSetting.get('fileRename')
        fileRenameSet = ModelSetting.get('fileRenameSet')
        

        ext = file.split(".")[-1]

        if ext.upper() in "MP3|FLAC|M4A":

            #인코딩 변경
            subprocess.check_output (['mid3iconv', '-e', 'cp949', os.path.join(file)])
            
            if os.path.isfile(file):
                logger.debug("파일존재 확인"  + file)
                
                tags = LogicNormal.getTagInfo(file)
                
                if tags == {} :
                    logger.debug("태그정보 없음.")
                    newFolderPath = os.path.join(err_path, "nonTAG")
                    newFilePath = os.path.join(newFolderPath, os.path.basename(file))
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    LogicNormal.procSave("4" , "", "", "", "", "", "", "", realFilePath)
                    return
                
                titlaByTag = tags['titlaByTag']
                artistByTag = tags['artistByTag']
                albumByTag = tags['albumByTag']

                logger.debug( "titlaByTag : " + titlaByTag)
                logger.debug( "artistByTag : " + artistByTag)
                logger.debug( "albumByTag : " + albumByTag)

                searchKey = titlaByTag + " " + artistByTag
                searchKey = re.sub('\([\s\S]+\)', '', searchKey).strip()
                
                logger.debug("검색어 "  + searchKey )
                
                #목록검색
                url = 'https://m.app.melon.com/search/mobile4web/searchsong_list.htm?cpId=WP10&cpKey=&memberKey=0&keyword='
                url = '%s%s' % (url, urllib.quote(searchKey.encode('utf8')))
                
                logger.debug( "url : " + url)

                data = LogicNormal.get_html(url)
                tree = html.fromstring(data)

                lis = tree.xpath('/html/body/div[1]/form/ul/li')

                match = False

                title = ""
                artist = ""
                album = ""

                for li in lis:
                    
                    title = li.get('d-songname').strip().upper()
                    artist = re.sub('\([\s\S]+\)', '', li.get('d-artistname')).strip().upper()
                    album = re.sub('\([\s\S]+\)', '', li.get('d-albumname')).strip().upper()

                    titleMaxLength = 0
                    if len(titlaByTag) <= len(title):
                        titleMaxLength = len(title)
                    else:
                        titleMaxLength = len(titlaByTag)
                    
                    artistMaxLength = 0
                    if len(artistByTag) <= len(artist):
                        artistMaxLength = len(artist)
                    else:
                        artistMaxLength = len(artistByTag)

                    albumMaxLength = 0
                    if len(albumByTag) <= len(album):
                        albumMaxLength = len(album)
                    else:
                        albumMaxLength = len(albumByTag)
                    
                    logger.debug( "titlaByTag : " + str( titlaByTag )  + "|| title : " + str( title) + " || titleMaxLength : " + str( titleMaxLength) )
                    logger.debug( "artistByTag : " + str( artistByTag ) + "|| artist : " + str( artist) + " || artistMaxLength : " + str( artistMaxLength) )
                    logger.debug( "albumByTag : " + str( albumByTag ) + "|| album : " + str( album) + "|| albumMaxLength : " + str( albumMaxLength) )
                        
                    titlelcs = LogicNormal.lcs(titlaByTag, title)
                    artistlcs = LogicNormal.lcs(artistByTag, artist)
                    albumlcs = LogicNormal.lcs(albumByTag, album)
                    logger.debug( " PASS" )
                    return
                    titleSimilarity = ( float(titlelcs) / float(titleMaxLength) ) * 100
                    artistSimilarity = ( float(artistlcs) / float(artistMaxLength) ) * 100
                    albumSimilarity = ( float(albumlcs) / float(albumMaxLength) ) * 100
                    
                    logger.debug( "titlaByTag : " + str( titlaByTag )  + "|| title : " + str( title) + " || titleMaxLength : " + str( titleMaxLength) + " || titlelcs : " + str( titlelcs ) + " || titleSimilarity : " + str( titleSimilarity))
                    logger.debug( "artistByTag : " + str( artistByTag ) + "|| artist : " + str( artist) + " || artistMaxLength : " + str( artistMaxLength) + " || artistlcs : " + str( artistlcs ) + " || artistSimilarity : " + str( artistSimilarity))
                    logger.debug( "albumByTag : " + str( albumByTag ) + "|| album : " + str( album) + "|| albumMaxLength : " + str( albumMaxLength) + " || albumlcs : " + str( albumlcs ) + " || albumSimilarity : " + str( albumSimilarity))
                    logger.debug( "------------------------------------")
                    
                    if ( titleSimilarity + artistSimilarity + albumSimilarity ) > int(maxCost) and ( titleSimilarity > 0 and artistSimilarity > 0 and albumSimilarity > int(singleCost) ) :

                        songId = li.get('d-songid').strip()
                        albumId = li.get('d-albumid').strip()

                        tags = LogicNormal.getSongTag(songId, albumId)
                        

                        #제목
                        title = tags['title']
                        #아티스트
                        artist = tags['artist']
                        #앨범
                        album = tags['album']
                        #트랙
                        track = tags['track']
                        #발매년도
                        year = tags['year']
                        #장르
                        genre = tags['genre']

                        folderStructure = folderStructure.replace('%title%', title)
                        folderStructure = folderStructure.replace('%artist%', artist)
                        folderStructure = folderStructure.replace('%album%', album)
                        folderStructure = folderStructure.replace('%year%', year)
                        folderStructure = folderStructure.replace('%genre%', genre)
                        
                        #newFolderPath = os.path.join(organize_path, folderStructure)
                        newFolderPath = os.path.join(organize_path, os.path.sep.join(folderStructure.split('/')))

                        if ModelSetting.get_bool('fileRename'):
                            fileRenameSet = fileRenameSet.replace('%title%', title)
                            fileRenameSet = fileRenameSet.replace('%artist%', artist)
                            fileRenameSet = fileRenameSet.replace('%album%', album)
                            fileRenameSet = fileRenameSet.replace('%track%', track)
                            fileRenameSet = fileRenameSet.replace('%year%', year)
                            fileRenameSet = fileRenameSet.replace('%genre%', genre)
                            
                            #fileRenameSet = os.path.join(newFolderPath,fileRenameSet)
                            fileRenameSet = os.path.join(newFolderPath,'%s%s' % (fileRenameSet, os.path.splitext(file)[1]))
                        else:
                            fileRenameSet = os.path.basename(file)
                        
                        newFilePath = os.path.join(newFolderPath, fileRenameSet )
                        newFolderPath = newFolderPath.replace('"',"'")
                        
                        match = True
                        
                        if os.path.isfile(newFilePath):
                            logger.debug("이미 파일있음" + file)
                            newFolderPath = os.path.join( err_path, "fileDupe" )
                            newFilePath = os.path.join( newFolderPath, os.path.basename(file) )
                            realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                            LogicNormal.procSave("2" , title, artist, album, titlaByTag, artistByTag, albumByTag, searchKey, realFilePath)
                            return
                        else:
                            realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                            LogicNormal.procSave("1" , title, artist, album, titlaByTag, artistByTag, albumByTag, searchKey, realFilePath)
                            return
                    
                if len(lis) < 1 or not match:
                    
                    newFolderPath = os.path.join( err_path, "nonSearch" )
                    newFilePath = os.path.join( newFolderPath, os.path.basename(file) )
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    status = ""
                    if len(lis) < 1 :
                        status = "5"
                    else:
                        status = "3"
                    logger.debug(status)
                    LogicNormal.procSave(status , title, artist, album, titlaByTag, artistByTag, albumByTag, searchKey, realFilePath)
            else:
                logger.debug("파일존재 미확인")
        else:
            logger.debug("MP3 아님 " + file)
            if notMp3delete == "True":
                logger.debug("삭제 처리")
                os.remove(file)
            

        logger.debug("================================")

    @staticmethod
    def getTagInfo(file):
        
        ext = file.split(".")[-1]

        tagsRtn = {}
        try:
            if ext.upper() == "MP3":
                audio = MP3(file)
                if "title" not in audio.tags.keys() or "artist" not in audio.tags.keys() or "album" not in audio.tags.keys():
                    return tagsRtn
                else:
                    tagsRtn['titlaByTag'] = audio.tags['title'][0].upper().strip()
                    tagsRtn['artistByTag'] = audio.tags['artist'][0].upper().strip()
                    tagsRtn['albumByTag'] = audio["album"][0].upper().strip()
            if "M4A" == ext.upper() :
                tags = MP4(file)
                tagsRtn['titlaByTag'] = str( tags.get('\xa9nam')[0] ).upper().strip()
                tagsRtn['artistByTag'] = str( tags.get('\xa9ART')[0] ).upper().strip()
                tagsRtn['albumByTag'] = str( tags.get('\xa9alb')[0] ).upper().strip()
            if "FLAC" == ext.upper() :
                tags = FLAC(file)
                tagsRtn['titlaByTag'] = str( tags.get('title')[0] ).upper().strip()
                tagsRtn['artistByTag'] = str( tags.get('artist')[0] ).upper().strip()
                tagsRtn['albumByTag'] = str( tags.get('album')[0] ).upper().strip()
        except Exception as e:
            logger.debug('Exception:%s', e)
            logger.debug(traceback.format_exc())

        return tagsRtn
    
    @staticmethod
    def getSongTag(songId, albumId):
        
        allTag = {}

        url = 'https://m.app.melon.com/song/detail.htm?songId='
        url = '%s%s' % (url, urllib.quote(songId))
        
        data = LogicNormal.get_html(url)
        tree = html.fromstring(data)

        #제목
        title = ""
        h1 = tree.xpath('/html/body/div[1]/article/div[2]/div/h1')[0]
        title = h1.text.strip()
        allTag['title'] = title
        #logger.debug( "제목 : " + title )

        #아티스트
        artist = ""
        p = tree.xpath('/html/body/div[1]/article/div[2]/div/p')[0]
        artist = p.text.strip()
        allTag['artist'] = artist
        #logger.debug( "아티스트 : " + artist )

        #장르
        genre = ""
        span = tree.xpath('/html/body/div[1]/article/div[2]/ul/li[1]/span[2]')[0]
        genre = span.text.strip()
        allTag['genre'] = genre
        #logger.debug( "장르 : " + genre )


        
        url = 'https://m.app.melon.com/album/music.htm?albumId='
        url = '%s%s' % (url, urllib.quote(albumId))
        
        data = LogicNormal.get_html(url)
        tree = html.fromstring(data)

        p = tree.xpath('/html/body/section/div[2]/div[1]/div/div[2]/p[2]')
        year = p[0].text[:4]
        #제작년도
        allTag['year'] = year
        #logger.debug( "제작년도 : " + year )
        
        #트랙
        track = "00"
        lis = tree.xpath('/html/body/div[1]/article/div[2]/ul/li')
        for i in range(1, len(lis)):
            p = tree.xpath('/html/body/div[1]/article/div[2]/ul/li[%s]/div[2]/div/a/p' % i)[0]
            if p.text.strip() == title:
                div = tree.xpath('/html/body/div[1]/article/div[2]/ul/li[%s]/div[1]' % i)[0]
                track = div.text_content().strip()
        allTag['track'] = track
        #logger.debug( "트랙 : " + track )
        
        #앨범이미지
        albumImage = ""
        meta = tree.xpath('/html/head/meta[6]')[0]
        albumImage = meta.attrib.get("content")
        allTag['albumImage'] = albumImage
        #logger.debug( "앨범이미지 : " + albumImage )

        #앨범
        album = ""
        p = tree.xpath('/html/body/section/div[2]/div[1]/div/div[2]/p[1]')[0]
        album = p.text.strip()
        allTag['album'] = album
        #logger.debug( "앨범 : " + album )

        #가사
        url = 'https://m.app.melon.com/song/lyrics.htm?songId='
        url = '%s%s' % (url, urllib.quote(songId))
        
        data = LogicNormal.get_html(url)
        tree = html.fromstring(data)
        
        div = tree.xpath('/html/body/div[1]/article/div[2]/div[2]')[0]
        from lxml.etree import tostring as htmlstring
        lyrics = htmlstring(div, encoding='utf8')
        lyrics = lyrics.replace('<div class="lyrics">',"")
        lyrics = lyrics.replace("&#13;","")
        lyrics = lyrics.replace("</div>","")
        lyrics = lyrics.replace("<br/>","\n").strip()
        allTag['lyrics'] = lyrics
        #logger.debug( "가사 : " + lyrics )

        return allTag

    @staticmethod
    def debugTest():

        logger.debug("DEBUG TEST")



        LogicNormal.getSongTag("1785912", "362766")
        return
        #logger.debug("file : " + str( file ))
        
        


        
        
        
        
        
