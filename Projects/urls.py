from . import views 
from django.urls import path

urlpatterns = [

    # getProjectDetails 
        path('getProjectDetails',views.getProjectDetails,name="getProjectDetails"),
        path('getProjects',views.getProjects,name="getProjects")

]