from django.urls import path,reverse_lazy
from django.contrib.auth import views as auth_views

from . import views 

urlpatterns = [
    path('Documents/', views.Document_list, name='Documents'),
    path('add-document/',views.upload,name='add-document'),
    path('upload-file/',views.upload_file,name='upload-file'),
    path('delete-document/<int:id>/',views.delete_document,name='delete-document'),
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
    path('lessonlearnt/',views.lessonlearnts,name='lessonlearnt'),                
    path('delete-lesson/<int:id>/',views.delete_lesson,name='delete-lesson'),
    path('lesson/',views.lesson,name='lesson'),
    path('edit-lesson/',views.edit_lesson,name='edit_lesson'),
    path('category/',views.categorys,name='category'),
    path('delete-category/<int:id>/',views.delete_category,name='delete-category'),
# ----------------------------------------------------------------------
    path('suggestion/',views.suggestion,name='suggestion'),
]