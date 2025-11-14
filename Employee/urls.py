from django.urls import path,reverse_lazy

from . import views 

urlpatterns = [
        
    path('login_view', views.loginUser, name='login_view'),  
    path('index/', views.index, name='index'),
    path('signup/', views.signup, name='signup'),

    path('getUsers/', views.getUsers, name='getUsers'),
    path('employee-details/', views.employeeDetails, name='employeeDetails'),
    path('edit-employee/', views.editEmployee, name='edit-employee'),
    path('delete-employee/', views.deleteEmployee, name='delete-employee'),

    # usermanagement
    path('getUserManagementSettings/', views.getUserManagementSettings, name='getUserManagementSettings'),
    path('getUserManagementData/', views.getUserManagementData, name='getUserManagementData'),
    
    # user permissions
    path('userPermissions/', views.userPermissions, name='userPermissions'),
    path('getUserPermissionsData/', views.getUserPermissionsData, name='getUserPermissionsData'),

    # home
    path('getpermissionList/', views.getpermissionList, name='getpermissionList'),
]