from . import views 
from django.urls import path

urlpatterns = [

    # weeklyTimesheetStatus 
        path('weeklyTimesheetStatus',views.weeklyTimesheetStatus,name="weeklyTimesheetStatus"),
        path('getWeeklyTimesheetStatus',views.getWeeklyTimesheetStatus,name="getWeeklyTimesheetStatus"),
        path('getDelayedTimesheet',views.getDelayedTimesheet,name="getDelayedTimesheet"),
        
        path('getNonSubmittData',views.getNonSubmittData, name='getNonSubmittData'),
        path('getConsolidatedReportData',views.getConsolidatedReportData, name='getConsolidatedReportData'),
    # actual vs budget
        path('timeBudgetAnalysis/',views.timeBudgetAnalysis,name='timeBudgetAnalysis'),
    # overview  
        path('timesheet_analysis/',views.timesheet_analysis, name ='timesheet_analysis'),
        path('ajax/getTimesheetLogs',views.getTimesheetLogs,name ='getTimesheetLogs'),
        path('taskwiseActualBudgetDatafun',views.taskwiseActualBudgetDatafun,name ='taskwiseActualBudgetDatafun'),
    # summary 
        path('OverallTimesheetLog/',views.OverallTimesheetLog, name ='OverallTimesheetLog'),
    # project overview
        path('all-project-analysis/',views.allProjectAnalysis, name= 'all-project-analysis'),
    # task overview
        path('task_Analysis/',views.task_analysis, name ='task_Analysis'),
        
]