from django.db import models
from django.contrib.auth.models import AbstractUser,Group
from django.db.models.deletion import CASCADE

# Create your models here.

class Role(models.Model):
    name = models.CharField(max_length=500,default="",null=False)

class JobTitles(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True, default=None)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

class users(AbstractUser):
    phone = models.CharField(max_length=10,null=True,default=None,blank= True,)
    designation = models.CharField(max_length=30,blank= True)
    # need to remove null= true in role
    # role = models.CharField(max_length=30,null=True,blank= True,default = None)
    jobtitle = models.ForeignKey(JobTitles, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    reporting_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    resigned_date = models.DateTimeField(default=None, null=True, blank=True) 
    
    def __str__(self) :
        return self.username
    
class modules(models.Model):
    name = models.CharField(max_length=500,default="",null=False)

class page(models.Model):
    name = models.CharField(max_length=500,default="",null=False)
    pageURL = models.CharField(max_length=500,default="",null=False)
    module = models.ForeignKey(modules, related_name='modules',on_delete=CASCADE)

class PageGroup(models.Model):
    page = models.ForeignKey(page, on_delete=models.CASCADE)
    jobtitle = models.ForeignKey(JobTitles, on_delete=models.CASCADE)

class OtherPermissions(models.Model):
    jobtitle = models.ForeignKey(JobTitles, on_delete=models.CASCADE)
    exclude = models.BooleanField(default=False)
    dailyEmail = models.BooleanField(default=False)
    weeklyEmail = models.BooleanField(default=False)
    notSubmittedSummaryMail = models.BooleanField(default=False)
    hoursRestriction = models.BooleanField(default=False)





    
