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

    nonTag = False
    @staticmethod
    def scheduler_function():
        # 자동 추가 목록에 따라 큐에 집어넣음.
        try:
            download_path = ModelSetting.get('download_path')
            organize_path = ModelSetting.get('proc_path')
            interval = ModelSetting.get('interval')
            emptyFolderDelete = ModelSetting.get('emptyFolderDelete')

            dirList = []
            fileList = []
            for dir_path, dir_names, file_names in os.walk(download_path):
                rootpath = os.path.join(os.path.abspath(download_path), dir_path)
                
                if os.path.isdir(dir_path):
                    dirList.append(dir_path)

                for file in file_names:
                    try:
                        filepath = os.path.join(rootpath, file)

                        """
                        logger.debug('=================================DEBUG START=================================')
                        LogicNormal.debugTest(filepath)
                        logger.debug('=================================DEBUG END=================================')
                        """
                        LogicNormal.mp3FileProc(filepath)
                        time.sleep(int(interval))
                    except Exception as e:
                        newFolderPath = os.path.join(ModelSetting.get('err_path'), "ERR")
                        newFilePath = os.path.join(newFolderPath, os.path.basename(file))
                        realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                        #realFilePath = "test"
                        LogicNormal.procSave("ERR" , "", "", "", "", "", "", "", realFilePath)
                        logger.debug('Exception:%s', e)
                        logger.debug(traceback.format_exc())
            
            if ModelSetting.get_bool('emptyFolderDelete'):
                for dir_path in dirList:
                    if len(os.listdir(dir_path)) == 0:
                        os.rmdir(dir_path)

            logger.debug("===============END=================")
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def tagUpdate(req):

        
        #tags.save(filePath)
        
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
                """
                logger.debug( "tags : " + str(tags.keys()))
                logger.debug( "title : " + str(tags['\xa9nam']))
                logger.debug( "artist : " + str(tags['\xa9ART']))
                logger.debug( "album : " + str(tags['\xa9alb']))
                """
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

        #rep = '[-=.#/?:$}\"\“\”]'
        #a = re.sub(rep, '', a)
        #b = re.sub(rep, '', b)

        #logger.debug( "a : " + a + ", " + str(len(a)))
        #logger.debug( "b : " + b + ", " + str(len(b)))
        
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
        """
        fileName = os.path.basename(newFilePath)
        fileName = fileName.replace('"',"'")
        newFilePath = os.path.join( newFolderPath, fileName )
        logger.debug(originPath + " ===>> " + newFilePath)
        os.rename(originPath, newFilePath)
        """
        if os.path.exists(newFilePath):
            os.remove(newFilePath)
        import shutil
        shutil.move(originPath, newFilePath)
        

        logger.debug("파일이동 완료")
        return newFilePath
    @staticmethod
    def procSave(status , title, artist, album, titleByTag, artistByTag, albumByTag, searchKey, file):
        entity = {}
        entity['id'] = ""
        entity['status'] = status
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
        

        #인코딩 변경
        if platform.system() == 'Windows':
            file = file.encode('cp949')
        subprocess.check_output (['mid3iconv', '-e', 'cp949', os.path.join(file)])
        
        ext = file.split(".")[-1]

        if ext.upper() in "MP3|FLAC|M4A":

            if os.path.isfile(file):
                logger.debug("파일존재 확인"  + file)
                global nonTag
                nonTag = False
                
                tags = LogicNormal.getTagInfo(file)
                #logger.debug("tags : " + str( tags ))
                
                #if titlaByTag == "" or artistByTag == "" or albumByTag == "":
                #    nonTag = True
                
                if nonTag :
                    logger.debug("태그정보 없음.")
                    newFolderPath = os.path.join(err_path, "nonTAG")
                    newFilePath = os.path.join(newFolderPath, os.path.basename(file))
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    LogicNormal.procSave("태그정보 없음." , "", "", "", "", "", "", "", realFilePath)
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
                
                url = 'https://m.app.melon.com/search/mobile4web/searchsong_list.htm?cpId=WP10&cpKey=&memberKey=0&keyword='
                url = '%s%s' % (url, urllib.quote(searchKey.encode('utf8')))
                
                logger.debug( "url : " + url)

                data = LogicNormal.get_html(url)
                tree = html.fromstring(data)

                lis = tree.xpath('/html/body/div[1]/form/ul/li')

                #logger.debug( "li CNT : " + str(len( lis )) )
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
                    
                    logger.debug( "titlaByTag : " + str( titlaByTag )  )
                    logger.debug( "title : " + str( title)  )
                    logger.debug( "artistByTag : " + str( artistByTag )  )
                    logger.debug( "artist : " + str( artist)  )
                    logger.debug( "albumByTag : " + str( albumByTag )  )
                    logger.debug( "album : " + str( album)  )

                    logger.debug( "titleMaxLength : " + str( titleMaxLength)  )
                    logger.debug( "artistMaxLength : " + str( artistMaxLength)  )
                    logger.debug( "albumMaxLength : " + str( albumMaxLength)  )
                    
                    titlelcs = LogicNormal.lcs(titlaByTag, title)
                    artistlcs = LogicNormal.lcs(artistByTag, artist)
                    albumlcs = LogicNormal.lcs(albumByTag, album)
                    logger.debug( "titlelcs : " + str( titlelcs )  )
                    logger.debug( "artistlcs : " + str( artistlcs )  )
                    logger.debug( "albumlcs : " + str( albumlcs )  )
                    
                    titleSimilarity = ( float(titlelcs) / float(titleMaxLength) ) * 100
                    artistSimilarity = ( float(artistlcs) / float(artistMaxLength) ) * 100
                    albumSimilarity = ( float(albumlcs) / float(albumMaxLength) ) * 100
                    
                    
                    logger.debug( "titleSimilarity : " + str( titleSimilarity)  )
                    logger.debug( "artistSimilarity : " + str( artistSimilarity)  )
                    logger.debug( "albumSimilarity : " + str( albumSimilarity)  )
                    logger.debug( "------------------------------------")
                    
                    #logger.debug(audio["title"][0] + " == " + title + " / " + str( LogicNormal.OneEditApart(audio["title"][0].upper(), title.upper()) ))
                    #logger.debug(audio["artist"][0] + " == " + artist + " / " + str( LogicNormal.OneEditApart(audio["artist"][0].upper(), audio["artist"][0].split(",")[0].upper()) ))
    
                    if ( titleSimilarity + artistSimilarity + albumSimilarity ) > int(maxCost) and ( titleSimilarity > 0 and artistSimilarity > 0 and albumSimilarity > int(singleCost) ) :

                        title = li.get('d-songname').strip()
                        artist = li.get('d-artistname').strip()
                        album = li.get('d-albumname').strip()

                        folderStructure = folderStructure.replace('%title%', title)
                        folderStructure = folderStructure.replace('%artist%', artist)
                        folderStructure = folderStructure.replace('%album%', album)
                        newFolderPath = os.path.join(organize_path, folderStructure)

                        if ModelSetting.get_bool('fileRename'):
                            fileRenameSet = fileRenameSet.replace('%title%', title)
                            fileRenameSet = fileRenameSet.replace('%artist%', artist)
                            fileRenameSet = fileRenameSet.replace('%album%', album)
                            fileRenameSet = os.path.join(newFolderPath,fileRenameSet)
                        else:
                            fileRenameSet = os.path.basename(file)
                        
                        newFilePath = os.path.join(newFolderPath, fileRenameSet )
                        newFolderPath = newFolderPath.replace('"',"'")
                        
                        match = True
                        
                        if os.path.isfile(newFilePath):
                            logger.debug("이미 파일있음" + file)
                            newFolderPath = os.path.join( err_path, "fileDupe" )
                            newFilePath = os.path.join( newFolderPath, os.path.basename(file) )
                            #logger.debug( "newFilePath : " + newFilePath)
                            #logger.debug( "newFolderPath : " + newFolderPath)
                            realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                            LogicNormal.procSave("중복" , title, artist, album, titlaByTag, artistByTag, albumByTag, searchKey, realFilePath)
                            return
                        else:
                            #logger.debug( "newFilePath : " + newFilePath)
                            #logger.debug( "newFolderPath : " + newFolderPath)
                            realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                            LogicNormal.procSave("정상" , title, artist, album, titlaByTag, artistByTag, albumByTag, searchKey, realFilePath)
                            return
                    
                if len(lis) < 1 or not match:
                    
                    newFolderPath = os.path.join( err_path, "nonSearch" )
                    newFilePath = os.path.join( newFolderPath, os.path.basename(file) )
                    #logger.debug( "newFilePath : " + newFilePath)
                    #logger.debug( "newFolderPath : " + newFolderPath)
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    status = ""
                    if len(lis) < 1 :
                        status = "검색결과없음"
                    else:
                        status = "매칭실패"
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
        logger.debug("")
        logger.debug("")
        logger.debug("")
        logger.debug("")

    @staticmethod
    def getTagInfo(file):
        
        ext = file.split(".")[-1]

        tagsRtn = {}
        if ext.upper() == "MP3":
            try:
                audio = MP3(file)
                
                #for frame in mutagen.File(file).tags.keys():
                #    logger.debug(str(frame))
                if "title" not in audio.tags.keys() or "artist" not in audio.tags.keys() or "album" not in audio.tags.keys():
                    global nonTag
                    nonTag = True
                else:
                    tagsRtn['titlaByTag'] = audio.tags['title'][0].upper().strip()
                    tagsRtn['artistByTag'] = audio.tags['artist'][0].upper().strip()
                    tagsRtn['albumByTag'] = audio["album"][0].upper().strip()
                
            except Exception as e:
                nonTag = True
                logger.debug('Exception:%s', e)
                logger.debug(traceback.format_exc())
        if "M4A" == ext.upper() :
            
            tags = MP4(file)
            #logger.debug( "tags : " + str( tags.keys() ))
            #logger.debug( "title : " + str( tags.get('\xa9nam')[0] ))
            #logger.debug( "album : " + str( tags.get('\xa9alb')[0] ))
            #logger.debug( "artist : " + str( tags.get('\xa9ART')[0] ))
            tagsRtn['titlaByTag'] = str( tags.get('\xa9nam')[0] ).upper().strip()
            tagsRtn['artistByTag'] = str( tags.get('\xa9ART')[0] ).upper().strip()
            tagsRtn['albumByTag'] = str( tags.get('\xa9alb')[0] ).upper().strip()
        if "FLAC" == ext.upper() :

            tags = FLAC(file)
            #logger.debug( "tags : " + str( tags.keys() ))
            #logger.debug( "title : " + str( tags.get('title')[0] ))
            #logger.debug( "album : " + str( tags.get('album')[0] ))
            #logger.debug( "artist : " + str( tags.get('artist')[0] ))
            tagsRtn['titlaByTag'] = str( tags.get('title')[0] ).upper().strip()
            tagsRtn['artistByTag'] = str( tags.get('artist')[0] ).upper().strip()
            tagsRtn['albumByTag'] = str( tags.get('album')[0] ).upper().strip()

        #logger.debug( "tagsRtn['titlaByTag'] : " + tagsRtn['titlaByTag'])
        #logger.debug( "tagsRtn['titlaByTag'] : " + tagsRtn['titlaByTag'].decode("UTF-8"))
        #logger.debug( "tagsRtn['titlaByTag'] : " + tagsRtn['titlaByTag'].encode("UTF-8"))
        #logger.debug( "tagsRtn['artistByTag'] : " + tagsRtn['artistByTag'])
        #logger.debug( "tagsRtn['albumByTag'] : " + tagsRtn['albumByTag'])
        return tagsRtn
    @staticmethod
    def debugTest(file):

        #logger.debug( "file : " + str( file ))
        LogicNormal.getTagInfo(file)
        subprocess.check_output (['mid3iconv', '-e', 'cp949', os.path.join(file)])
        LogicNormal.getTagInfo(file)
        


