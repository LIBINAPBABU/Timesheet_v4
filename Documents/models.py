import os
# from turtle import title
from django.utils import timezone
from django.db import models
from .storage import OverwriteStorage

from ast import Try
from platform import mac_ver
from random import sample
from shutil import _ntuple_diskusage
from unicodedata import name
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models.deletion import CASCADE
from Employee.models import users

# Create your models here.
class document_manage(models.Model):
    document_name =models.CharField(max_length=100,default="",null=False)
    updated_date = models.DateField(default=timezone.now,null=False)
    version = models.CharField(max_length=10,default="",null=False)
    file = models.FileField(storage=OverwriteStorage(), upload_to='document/')

    def __str__(self):
        return self.fname
    
    def delete(self, *args,**kwargs) :
        self.file.delete()
        super().delete( *args,**kwargs)

    def file_path(instance, filename):
        return os.path.join('some_dir', str(instance.some_identifier), 'filename.ext')

class feeds(models.Model):
    date =models.DateField(default=timezone.now,null=False)
    title =models.CharField(max_length=100,default="Title",null=False)
    Description =models.CharField(max_length=500,default="",null=False)
    file = models.FileField(storage=OverwriteStorage(), upload_to='images/')

    def __str__(self):
        return self.title_Name
    
    def delete(self, *args,**kwargs) :
        self.file.delete()
        super().delete( *args,**kwargs)

    def file_path(instance, filename):
        return os.path.join('some_dir', str(instance.some_identifier), 'filename.ext')

class lessonlearnt(models.Model):
    Project=models.CharField(max_length=50)
    Category=models.CharField(max_length=50)
    Owner=models.CharField(max_length=100)
    Event=models.CharField(max_length=500)
    Limitations=models.CharField(max_length=500)
    Actions=models.CharField(max_length=500)
    file_lesson = models.FileField(storage=OverwriteStorage(), upload_to='lessonlearnt/',null=True, blank=True, default=None)
    Status=models.CharField(max_length=50)
    Remark=models.CharField(max_length=500)
    def __str__(self):
        return self.title_Name
    
    def file_path(instance, filename):
        return os.path.join('some_dir', str(instance.some_identifier), 'filename.ext')
   
class category_project(models.Model):
    Category=models.CharField(max_length=50,default="")

class Suggestion(models.Model):
    uid = models.ForeignKey(users, on_delete=CASCADE, db_index=True)  # Add index on uid
    created_date = models.DateTimeField(auto_now_add=True)
    
    suggestions = models.CharField(max_length=1500,default=None,null=False, blank=True)  
    suggestion_status = models.CharField(max_length=50, default=None, null=True)
    remarks = models.CharField(max_length=1500,default=None,null=True)