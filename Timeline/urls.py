from django.urls import path

from . import views 

urlpatterns = [
    ################### timsheet page ##################### 
        path('submission/', views.submission, name='submission'),
        path('ajax/get_time_sheet_templete',views.submission_templete ,name='get_time_sheet_templete'),
        path('fetch_quotations/',views.fetch_quotations,name='fetch_quotations'),
        path('assignUndefinedQuotation/',views.assignUndefinedQuotation,name='assignUndefinedQuotation'),
        path('fetchServiceMilestonesTasks/',views.fetchServiceMilestonesTasks,name='fetchServiceMilestonesTasks'),
                    
        path('unlock-timesheet/',views.unlock_timesheet,name='unlock-timesheet'),
        path('accept-unlock-request/',views.accept_unlock_request,name='accept-unlock-request'),
        path('reject-unlock-request/',views.reject_unlock_request,name='reject-unlock-request'),
        path('update-assigner/',views.update_assigner,name='update-assigner'),
        
    ################### approval page #####################
        path("allTimesheetLog",views.allTimesheetLog,name="allTimesheetLog"),
        path("get_summary_template",views.get_summary_template,name="get_summary_template"),
    ################### Email sscheduling ###################
        path('emailsend',views.emailsend,name='emailsend'),
        path('dailyRemainderEmail',views.dailyRemainderEmail,name='dailyRemainderEmail'),
        path('weeklyApprovalMail',views.weeklyApprovalMail,name='weeklyApprovalMail')
]