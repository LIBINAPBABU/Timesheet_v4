from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.

class users(AbstractUser):
    phone = models.CharField(max_length=10,null=True,default=None,blank= True,)
    designation = models.CharField(max_length=30,blank= True)
    # need to remove null= true in role
    role = models.CharField(max_length=30,null=True,blank= True,default = None)
    reporting_to =models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    resigned_date = models.DateTimeField(default=None, null=True, blank=True) 
    
    def __str__(self) :
        return self.username

    
