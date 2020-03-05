# -*- coding: utf-8 -*-
#########################################################
# python
import traceback
from datetime import datetime
import json
import os

# third-party
from sqlalchemy import or_, and_, func, not_, desc
from sqlalchemy.orm import backref

# sjva 공용
from framework import app, db, path_app_root
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from downloader import ModelDownloaderItem

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))
#########################################################
        
class ModelSetting(db.Model):
    __tablename__ = '%s_setting' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)
 
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    @staticmethod
    def get(key):
        try:
            return db.session.query(ModelSetting).filter_by(key=key).first().value.strip()
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
            
    
    @staticmethod
    def get_int(key):
        try:
            return int(ModelSetting.get(key))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def get_bool(key):
        try:
            return (ModelSetting.get(key) == 'True')
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def set(key, value):
        try:
            item = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
            if item is not None:
                item.value = value.strip()
                db.session.commit()
            else:
                db.session.add(ModelSetting(key, value.strip()))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def to_dict():
        try:
            return Util.db_list_to_dict(db.session.query(ModelSetting).all())
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())


    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                if key in ['scheduler', 'is_running']:
                    continue
                logger.debug('Key:%s Value:%s', key, value)
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True                  
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            logger.debug('Error Key:%s Value:%s', key, value)
            return False




class ModelItem(db.Model):
    __tablename__ = '%s_item' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    json = db.Column(db.JSON)
    created_time = db.Column(db.DateTime)

    status = db.Column(db.String)
    title = db.Column(db.String)
    artist = db.Column(db.String)
    album = db.Column(db.String)
    titleByTag = db.Column(db.String)
    artistByTag = db.Column(db.String)
    albumByTag = db.Column(db.String)
    filePath = db.Column(db.String)
    #inqueue_time = db.Column(db.DateTime)
    #start_time = db.Column(db.DateTime)
    #end_time = db.Column(db.DateTime)
    #status = db.Column(db.Integer) # 0:생성, 1:요청, 2:실패 11완료 12:파일잇음
    #str_status = db.Column(db.String)

    #title_id = db.Column(db.String)
    #episode_id = db.Column(db.String)
    
    #episode_title = db.Column(db.String)
    #download_count = db.Column(db.Integer)
    

    def __init__(self):
        self.created_time = datetime.now()
    
    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        #ret['start_time'] = self.start_time.strftime('%m-%d %H:%M:%S') if self.start_time is not None else None
        #ret['end_time'] = self.end_time.strftime('%m-%d %H:%M:%S') if self.end_time is not None else None

        return ret

    @staticmethod
    def save_as_dict(d):
        try:
            logger.debug(d)
            entity = ModelItem()
            entity.status = unicode(d['status'])
            entity.title = unicode(d['title'])
            entity.artist = unicode(d['artist'])
            entity.album = unicode(d['album'])
            entity.titleByTag = unicode(d['titleByTag'])
            entity.artistByTag = unicode(d['artistByTag'])
            entity.albumByTag = unicode(d['albumByTag'])
            entity.filePath = unicode(d['filePath'])
            db.session.add(entity)
            db.session.commit()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    @staticmethod
    def select(req):
        try:
            class_is = ModelItem
            ret = {}
            page = 1
            page_size = 30
            job_id = ''
            search = ''
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'search_word' in req.form:
                search = req.form['search_word']
            query = db.session.query(class_is)
            if search != '':
                query = query.filter(class_is.title.like('%'+search+'%'))
            query = query.order_by(desc(class_is.id))
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def get(id):
        try:
            entity = db.session.query(ModelItem).filter_by(id=id).with_for_update().first()
            return entity
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    """
    @staticmethod
    def update(req):
        try:
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
            
            entity = db.session.query(ModelItem).filter_by(id=id).with_for_update().first()
            filePath = entity.filePath
            LogicNormal.tagUpdate(filePath, title, artist, album)
            
            
            ret = {}
            ret['title'] = "test"
            return ret
            
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        ret['inqueue_time'] = self.inqueue_time.strftime('%m-%d %H:%M:%S') if self.inqueue_time is not None else None
        #ret['start_time'] = self.start_time.strftime('%m-%d %H:%M:%S') if self.start_time is not None else None
        #ret['end_time'] = self.end_time.strftime('%m-%d %H:%M:%S') if self.end_time is not None else None

        return ret

    @staticmethod
    def init(title_id, episode_id):
        try:
            entity = db.session.query(ModelItem).filter_by(title_id=title_id).filter_by(episode_id=episode_id).first()
            if entity is None:
                entity = ModelItem(title_id, episode_id)
                entity.inqueue_time = datetime.now()
                db.session.add(entity)
                db.session.commit()
            #else:
            #    if entity.status > 10:
            #        return None
            return entity.as_dict()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_list(by_dict=False):
        try:
            tmp = db.session.query(ModelItem).all()
            if by_dict:
                tmp = [x.as_dict() for x in tmp]
            return tmp
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    
    

    @staticmethod
    def delete(req):
        try:
            class_is = ModelItem
            db_id = int(req.form['id'])
            item = db.session.query(class_is).filter_by(id=db_id).first()
            if item is not None:
                db.session.delete(item)
                db.session.commit()
            return True
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    
    """