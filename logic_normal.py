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

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
import requests
from lxml import html
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3


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
                    filepath = os.path.join(rootpath, file)
                    LogicNormal.mp3FileProc(filepath)
                    time.sleep(int(interval))
            
            if emptyFolderDelete == "True":
                for dir_path in dirList:
                    if len(os.listdir(dir_path)) == 0:
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
            
            audio = EasyID3(filePath)

            audio["title"] = unicode(title)
            audio["artist"] = unicode(artist)
            audio["album"] = unicode(album)
            audio.save()
            logger.debug("파일처리시작"  + filePath)
            LogicNormal.mp3FileProc(filePath)
            

        ret = {}
        return ret

    @staticmethod
    def get_html(url, referer=None, stream=False):
        try:
            if LogicNormal.session is None:
                LogicNormal.session = requests.session()
            #logger.debug('get_html :%s', url)
            headers['Referer'] = '' if referer is None else referer
            
            page_content = LogicNormal.session.get(url, headers=headers)
            data = page_content.text
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return data
    
    @staticmethod
    def lcs(a, b):

        rep = '[-=.#/?:$}\"\“\”]'
        a = re.sub(rep, '', a)
        b = re.sub(rep, '', b)

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
        newPathStep = newFolderPath.split("/")
        newPathStepTmp = ""
        for step in newPathStep:
            newPathStepTmp = newPathStepTmp + "/" + step
            newPathStepTmp = newPathStepTmp.replace("//","/")
            if not os.path.isdir(newPathStepTmp):
                logger.debug("폴더 생성 : " + newPathStepTmp)
                os.makedirs(newPathStepTmp)
        logger.debug("파일이동 시작")
        

        #logger.debug("파일명체크 시작")
        fileName = newFilePath.replace(newFolderPath+"/","")
        fileName = fileName.replace('"',"'")
        fileName = fileName.replace('/','')
        #logger.debug("신규 파일명 :" + fileName) 
        newFilePath = newFolderPath+"/"+fileName
        #logger.debug("신규 파일경로명 :" + newFilePath) 
        #logger.debug("파일명체크 종료")
        logger.debug(originPath + " ===>> " + newFilePath)
        os.rename(originPath, newFilePath)
        logger.debug("파일이동 완료")
        return newFilePath.replace("//","/")
    @staticmethod
    def procSave(status , title, artist, album, titleByTag, artistByTag, albumByTag, file):
        entity = {}
        entity['id'] = ""
        entity['status'] = status
        entity['title'] = title
        entity['artist'] = artist
        entity['album'] = album
        entity['titleByTag'] = titleByTag
        entity['artistByTag'] = artistByTag
        entity['albumByTag'] = albumByTag
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
        

        ext = file.split(".")[-1]

        if ext.upper() == "MP3":

            if os.path.isfile(file):
                logger.debug("파일존재 확인"  + file)

                audio = EasyID3(file)
                
                if len(audio) < 1 :
                    logger.debug("태그정보 없음.")
                    newFolderPath = err_path+"/nonTAG"
                    newFilePath = newFolderPath + "/" + os.path.basename(file)
                    #logger.debug( "newFilePath : " + newFilePath)
                    #logger.debug( "newFolderPath : " + newFolderPath)
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    LogicNormal.procSave("태그정보 없음." , "", "", "", "", "", "", realFilePath)
                    return


                titlaByTag = ""
                artistByTag = ""
                albumByTag = ""

                try:
                    titlaByTag = audio["title"][0].upper().strip()
                    artistByTag = re.sub('\([\s\S]+\)', '', audio["artist"][0].upper()).strip()
                    albumByTag = audio["album"][0].upper().strip()
                except Exception as e:
                    logger.error('Exception:%s', e)
                    logger.error(traceback.format_exc())
                

                if titlaByTag == "" or artistByTag == "" or albumByTag == "":
                    logger.debug("태그정보 없음.")
                    newFolderPath = err_path+"/nonTAG"
                    newFilePath = newFolderPath + "/" + os.path.basename(file)
                    #logger.debug( "newFilePath : " + newFilePath)
                    #logger.debug( "newFolderPath : " + newFolderPath)
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    LogicNormal.procSave("태그정보 없음." , "", "", "", "", "", "", realFilePath)
                    return
                searchKey = audio["title"][0] + " " + audio["artist"][0].split(",")[0]
                searchKey = re.sub('\([\s\S]+\)', '', searchKey).strip()
                
                logger.debug("검색어 "  + searchKey )
                
                url = 'https://m.app.melon.com/search/mobile4web/searchsong_list.htm?cpId=WP10&cpKey=&memberKey=0&keyword='
                url = '%s%s' % (url, urllib.quote(searchKey.encode('utf8')))
                
                logger.debug( "url : " + url)

                data = LogicNormal.get_html(url)
                tree = html.fromstring(data)

                lis = tree.xpath('/html/body/div[1]/form/ul/li')

                logger.debug( "li CNT : " + str(len( lis )) )
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

                        newFolderPath = organize_path+"/"+artist+"/"+album
                        newFilePath = organize_path+"/"+artist+"/"+album+"/"+title+" - "+artist+".mp3"
                        newFolderPath = newFolderPath.replace('"',"'")
                        
                        match = True
                        
                        if os.path.isfile(newFilePath):
                            logger.debug("이미 파일있음" + file)
                            newFolderPath = err_path+"/fileDupe"
                            newFilePath = newFolderPath + "/" + os.path.basename(file)
                            #logger.debug( "newFilePath : " + newFilePath)
                            #logger.debug( "newFolderPath : " + newFolderPath)
                            realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                            LogicNormal.procSave("중복" , title, artist, album, titlaByTag, artistByTag, albumByTag, realFilePath)
                            return
                        else:
                            #logger.debug( "newFilePath : " + newFilePath)
                            #logger.debug( "newFolderPath : " + newFolderPath)
                            realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                            LogicNormal.procSave("정상" , title, artist, album, titlaByTag, artistByTag, albumByTag, realFilePath)
                            return
                    
                if len(lis) < 1 or not match:
                    
                    newFolderPath = err_path+"/nonSearch"
                    newFilePath = newFolderPath + "/" + os.path.basename(file)
                    #logger.debug( "newFilePath : " + newFilePath)
                    #logger.debug( "newFolderPath : " + newFolderPath)
                    realFilePath = LogicNormal.fileMove(file , newFolderPath, newFilePath)
                    status = ""
                    if len(lis) < 1 :
                        status = "검색결과없음"
                    else:
                        status = "매칭실패"
                    logger.debug(status)
                    LogicNormal.procSave(status , title, artist, album, titlaByTag, artistByTag, albumByTag, realFilePath)
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