# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
import threading
import subprocess

# third-party

# sjva 공용
from framework import db, scheduler, path_data, celery
from framework.job import Job
from framework.util import Util

# 패키지 
from .plugin import logger, package_name
from .model import ModelSetting, ModelItem

try:
    import asyncio
    from shazamio import Shazam
except:
    os.system("pip install shazamio")
    import asyncio
    from shazamio import Shazam
    
try:
    from .logic_normal import LogicNormal
except:
    os.system("pip install mutagen")
    from .logic_normal import LogicNormal




#from .logic_normal import LogicNormal
#########################################################

class Logic(object):
    db_default = {
        'db_version' : '1',
        'download_path' : os.path.join(path_data, package_name),
        'proc_path' : os.path.join(path_data, package_name),
        'err_path' : os.path.join(path_data, package_name),
        'maxCost' : '200',
        'singleCost' : '0',
        'schedulerInterval' : '60',
        'interval' : '5',
        'auto_start' : 'False',
        'emptyFolderDelete' : 'False',
        'notMp3delete' : 'False',
        'folderStructure' : '%artist%/%album%/',
        'fileRename' : 'False',
        'fileRenameSet' : '%track% - %title%',
        'isEncoding' : 'True',
        'isEncodingType' : 'MP3,M4A',
        'isDupeDel' : 'False',
        'isTagUpdate' : 'False',
        'genreExc' : '',
        'isShazam' : 'False'

    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
            
            Logic.migration()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        
    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            # mutagen 자동 설치
            #Logic.autoInstall()

            Logic.db_init()
            if ModelSetting.get_bool('auto_start'):
                Logic.scheduler_start()
            # 편의를 위해 json 파일 생성
            # from plugin import plugin_info
            # Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

            
            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def autoInstall():
        try:
            
            try:
                import mutagen
                from .logic_normal import LogicNormal
            except:
                os.system("pip install mutagen")
                from .logic_normal import LogicNormal
            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def scheduler_start():
        try:
            logger.debug('%s scheduler_start' % package_name)
            job = Job(package_name, package_name, ModelSetting.get('schedulerInterval'), Logic.scheduler_function, u"음악정리", False)
            scheduler.add_job_instance(job)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def scheduler_stop():
        try:
            logger.debug('%s scheduler_stop' % package_name)
            scheduler.remove_job(package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
           

    @staticmethod
    def scheduler_function():
        try:
            #LogicNormal.scheduler_function()
            from framework import app
            if app.config['config']['use_celery']:
                result = LogicNormal.scheduler_function.apply_async()
                result.get()
            else:
                LogicNormal.scheduler_function()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def reset_db():
        try:
            from .model import ModelItem
            db.session.query(ModelItem).delete()
            db.session.commit()
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False


    @staticmethod
    def one_execute():
        try:
            if scheduler.is_include(package_name):
                if scheduler.is_running(package_name):
                    ret = 'is_running'
                else:
                    scheduler.execute_job(package_name)
                    ret = 'scheduler'
            else:
                def func():
                    #time.sleep(2)
                    Logic.scheduler_function()
                threading.Thread(target=func, args=()).start()
                ret = 'thread'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret


    @staticmethod
    def process_telegram_data(data):
        try:
            logger.debug(data)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def migration():
        try:
            ModelItem.migration()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())