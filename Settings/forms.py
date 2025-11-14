from django import forms
from django.db import models
from django.db.models import fields
from django.db.models.base import Model
from .models import Milestone,Task

class templates_milestone_form(forms.ModelForm):
    class Meta:
        model = Milestone
        fields =['name']

class templates_task_form(forms.ModelForm):
    class Meta:
        model = Task
        fields =['mid','name']