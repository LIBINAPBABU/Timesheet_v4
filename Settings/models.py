# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.db.models.deletion import CASCADE

class CostCategory(models.Model):
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(unique=True, max_length=10)
    is_free_text = models.TextField(blank=True, null=True)  # This field type is a guess.
    name = models.CharField(unique=True, max_length=100)
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    version_lock = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cost_category'

class CostMaster(models.Model):
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(unique=True, max_length=100, blank=True, null=True)
    name = models.CharField(unique=True, max_length=100)
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    version_lock = models.BigIntegerField(blank=True, null=True)
    cost_category = models.ForeignKey(CostCategory, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'cost_master'

class Milestone(models.Model):
    name = models.CharField(max_length=1024,default="",null=False)

class Task(models.Model):
    name = models.CharField(max_length=1024,default="",null=False)
    mid = models.ForeignKey(Milestone, related_name='milestones',on_delete=CASCADE)

class phases(models.Model):
    name = models.CharField(max_length=1024,default="",null=False)

class phaseCategory(models.Model):
    category = models.PositiveIntegerField(default="",null=False)
    phases = models.ForeignKey(phases,on_delete=CASCADE)