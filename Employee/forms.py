from typing import ClassVar
import django
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core import validators
from django.db import models
from django.db.models.enums import Choices
from django.forms import fields, widgets
from django import forms
from .models import users
from django.core.validators import RegexValidator

class usersForm(UserCreationForm):
    username = forms.CharField(initial="")
    email = forms.CharField(initial="")
    # role_choices = (("Lead","Lead"),("Manager","Manager"),("Employee","Employee"))
    # role = forms.ChoiceField(choices=role_choices)
    alphanumeric = RegexValidator(r'^[0-9]*$', 'Invalid Mobile Number')
    phone = forms.CharField(max_length=10,min_length = 10,validators=[alphanumeric],initial="")
    class Meta:
        model = users
        fields = ['username','first_name','last_name','email','phone','designation']
        
    

