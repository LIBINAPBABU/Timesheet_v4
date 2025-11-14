from django.urls import path

from . import views 

urlpatterns = [
        
    path('list-templates/', views.list_templates, name='list-templates'),
    path('getTemplateData/', views.getTemplateData, name='getTemplateData'),
    path('Add-milestone/',views.add_milestone,name='Add-milestone'),
    path('Add-task/',views.add_task,name='Add-task'),

    path('groupingCostCategory/',views.groupingCostCategory,name='groupingCostCategory'),
    path('getListData/',views.getListData,name='getListData'),

]