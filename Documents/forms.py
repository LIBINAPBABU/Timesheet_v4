from django.utils import timezone
from django import forms
from django.db.models import fields
from django.forms.fields import CharField
from django.forms.forms import Form
from .models import document_manage,feeds,lessonlearnt,category_project


class document_mange_form(forms.ModelForm):
   class Meta:
        model = document_manage
        fields =['document_name','updated_date','version','file']

class feeds_form(forms.ModelForm):
   class Meta:
      model = feeds
      fields =['title','Description','file']

class lessonlearnt_form(forms.ModelForm):
   class Meta:
      model = lessonlearnt
      fields =['Project','Category','Owner','Event','Limitations','Actions','file_lesson','Status','Remark']
class category_form(forms.ModelForm):
   class Meta:
      model = category_project
      fields =['Category']