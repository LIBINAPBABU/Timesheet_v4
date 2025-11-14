from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from Employee.models import users
from django.http import HttpResponse, JsonResponse
from Timeline.models import TimesheetSubmission,TimesheetStatus
from Timeline.views import secondToHours
from Timeline.models import Quotation,TimesheetSubmission,TimesheetStatus,Submission,Customer,AssignedTask
from collections import defaultdict
from Employee.decorators import unathenticated
from django.db.models import Q,F,Sum,Case, When, Value, CharField, Subquery, OuterRef,ExpressionWrapper, FloatField,Count 
from django.views.decorators.csrf import csrf_exempt,csrf_protect
from datetime import date, timedelta, datetime
from django.db.models.functions import ExtractDay,Cast,Coalesce,Concat,ExtractWeek,ExtractYear,TruncDate

from django_mysql.models import GroupConcat
from django.db.models import CharField, Value as V
from itertools import chain
import json

# weeklyTimesheetStatus analysys
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def weeklyTimesheetStatus(request):
    return render(request,'weeklyTimesheetStatus.html',{"module":"analysys"})

@csrf_exempt
def getWeeklyTimesheetStatus(request):
    # Get the current date and time
    current_date = datetime.today()
    current_weekyear = current_date.year
    current_weekday = current_date.weekday()

    # Calculate the difference from Saturday (5 = Saturday)
    days_to_saturday = (5 - current_weekday) % 7

    # Calculate the start of the week (Saturday)
    if days_to_saturday == 0:
        week_start_date = current_date  # Today is Saturday
    else:
        week_start_date = current_date - timedelta(days=(current_weekday + 2) % 7)

    employees = users.objects.prefetch_related('timesheetstatus')\
                                            .filter(
                                                is_active=True
                                                # timesheetstatus__weekyear__isnull=False,
                                                # timesheetstatus__weeknumber__isnull=False
                                            )\
                                            .exclude(role__in=['Consultant', 'Admin', 'HR', 'CEO'])\
                                            .annotate(
                                                joinedWeek=ExtractWeek('date_joined'),
                                                joinedYear=ExtractYear('date_joined'),
                                                timesheet_status = F('timesheetstatus__timesheet_status'),
                                                submission_status=Coalesce(F('timesheetstatus__submission_status'), Value(False)),
                                                action_status=Coalesce(F('timesheetstatus__action_status'), Value(False)),
                                                weeknumber=F('timesheetstatus__weeknumber'),
                                                weekyear=F('timesheetstatus__weekyear')
                                            )\
                                            .values('first_name', 'reporting_to', 'id', 'joinedWeek', 'joinedYear',
                                                    'submission_status', 'action_status', 'timesheet_status','weeknumber', 'weekyear').order_by('first_name')
    
    if request.user.role not in ['Consultant', 'Admin','HR','CEO']:
        employees = employees.filter(Q(reporting_to = request.user.id))
    
    result = defaultdict(lambda: defaultdict(dict))
    for item in employees:
        result[item['id']]['first_name'] = item['first_name']
        result[item['id']][item['weeknumber']] = { "action_status" : item['action_status'],
                                                  "approval_status":"delayed" if item['weeknumber'] is None else  getApprovalStatus(item['id'],item['weeknumber'],item['weekyear']),
                                                  "submission_status" : item['submission_status'],
                                                  "timesheet_status": item['timesheet_status']}
        result[item['id']]['joinedWeek'] = item['joinedWeek']
        result[item['id']]['joinedYear'] = item['joinedYear']
        result[item['id']]['weekYear'] = item['weekyear']
    result = dict(result)
    return JsonResponse({"employees":result,
                         'year':current_weekyear,
                         'current_week':int(week_start_date.strftime("%V"))})

def getApprovalStatus(user,weeknumber,year):

# get start date from weeknumber and year
    start_Date = datetime.strptime(f'{year} {int(weeknumber):02d} 1', '%Y %W %w') - timedelta(days=2)
   
    #Get the approval status of the employee for the week
    approval_status = Submission.objects.filter(
        assignId__assignTo=user,date__range =[start_Date, start_Date + timedelta(days=6)]
    ).aggregate(
        total=Count('assignId'),
        approved_true=Count('assignId', filter=Q(approved_status=True)),
        approved_false=Count('assignId', filter=Q(approved_status=False)),
    )
    # Decide status based on the aggregation
    if approval_status['approved_true'] and approval_status['approved_false']:
        timesheetstatus = 'missed'
    elif approval_status['approved_true'] == approval_status['total'] and approval_status['total'] != 0:
        timesheetstatus = 'ontime'
    elif approval_status['approved_false'] == approval_status['total'] and approval_status['total'] != 0:
        timesheetstatus = 'delayed'
    else:
        timesheetstatus = 'unknown'
    # print("status",timesheetstatus)
    return timesheetstatus    



@csrf_exempt
def getDelayedTimesheet(request):
    # get post data
    if request.method == 'POST':
        empId = request.POST.get('empId')
        weekYear = request.POST.get('weekYear')
        weekNumber = request.POST.get('weekNum')
        # get the week start date from week year and week number
        if weekYear and weekNumber:
            try:
                # Make sure weekNumber is two digits and minus 2 days to get the start date
                week_start_date = datetime.strptime(f'{weekYear} {int(weekNumber):02d} 1', '%Y %W %w') - timedelta(days=2)
                #  get all approved details  of employee for the week
                timesheetstatus = Submission.objects.filter(assignId__assignTo = empId,
                                                      date__range =[week_start_date, week_start_date + timedelta(days=6)]
                                                      ).annotate(updated_date_only=TruncDate('updated_date'))\
                                                        .values('approved_status',
                                                        'updated_date_only',
                                                        'status',
                                                        approvedBy__first_name =F('assignId__assignBy__first_name'))\
                                                        .distinct()
        

                print("timesheetstatus",timesheetstatus)
            except ValueError as e:
                print("Error parsing date:", e)
                return JsonResponse({"error": "Invalid week year or week number."}, status=400)
    return JsonResponse({"success":True ,"timesheetstatus": list(timesheetstatus)},status =200)   
        

# Time Budget analysis new without chart (card presentation only)
@csrf_protect
@csrf_exempt
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def timeBudgetAnalysis(request):

    # customer_code_subquery = Customer.objects.filter(

    # name=OuterRef('customer_name')  .annotate()

    # ).values('code')[:1]

    data = Quotation.objects.using('erp').values(
                                                'quotation_no',
                                                'customer_name'
                                            ).annotate(
                                                budget=Sum(F('quotationcost__quantity')) * 9,
                                                project_label=Case(
                                                    When(custom_project_name__isnull=False, then='custom_project_name'),
                                                    When(project__name__isnull=False, then='project__name'),
                                                    default=Value(""),
                                                    output_field=CharField()
                                                )
                                            ).filter(
                                                quotation_no__isnull=False,
                                                customer_name__isnull=False #,status="Confirmed"
                                            ).exclude(
                                                budget=0
                                            ).distinct()
    
    if request.method == 'POST': 
        quotationNum = request.POST.get('quotationNum')
        task_list=list(Submission.objects
                .values(quotation=F('assignId__quotation'),
                        taskName=F('assignId__taskName'))
                .filter(quotation = quotationNum)
                .annotate(act_hrs = Sum('hours'))
                .annotate(Count('assignId__assignTo',distinct=True))
                .order_by('assignId__taskName')
            )
        args={'quotation_no':quotationNum}
        data = getActualBudgetList(task_list,args)
        return JsonResponse({"taskWiseData":data})
    
    # Get actual hours annotate(quotation=F('assignId__quotation')
    submissions = (
        Submission.objects
        .exclude(assignId__quotation="Non project")
        .values(quotation=F('assignId__quotation'))  # group by quotation
        .annotate(
            emp_count=Count('assignId__assignTo', distinct=True),  # count unique employees
            actual=Sum('hours')  # total hours
        )
    )

    actualHours = {}

    for i in submissions:
        actualHours[i['quotation']] = {
            "act_hrs": float(secondToHours(i['actual'])[:-6].replace(":", ".")),
            "emp_count": i['emp_count']
        }

    # Calculate delta and percentage variance
    for i in data:

        i['name'] = i['quotation_no'] +' '+i['customer_name'] +' ' + i['project_label'] if  i['project_label'] else i['quotation_no'] + ' ' +i['customer_name']
        i['actual'] = actualHours.get(i['quotation_no'],{}).get("act_hrs", 0)
        i['employee_count'] = actualHours.get(i['quotation_no'],{}).get("emp_count", 0)
        i['budget'] = i['budget'] or 0  # Set to 0 if None

        i['delta'] = i['actual'] - i['budget']  # Difference
        i['percent'] = round((i['delta'] / i['budget'] * 100) ,2)if i['budget'] > 0 else 0  # Percentage variance

    return render(request,'time_budget_analysis.html',{"module":"analysys",
                                                       'data':list(data)})




# Overview
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def timesheet_analysis(request):
    return render(request,'timesheet_analysis.html',{"module":"analysys"}) 

@csrf_exempt
@login_required(login_url='home')
@unathenticated
def getTimesheetLogs(request):
    from_date = datetime.strftime( datetime.now(),'%Y-%m-01')
    to_date = datetime.strftime( datetime.now(),'%Y-%m-%d')
    user = request.user
    if request.method =='POST':
        from_date =request.POST['from_date']
        to_date  =request.POST['to_date']
      
    total_hrs,timeSheet_logs = timesheet_daily_hours(from_date,to_date,user)
  
    chartdata,task_List = overview_chart_data(from_date,to_date,user)

    project_hour = project_hours(from_date,to_date,user)
 
    taskwiseActualBudgetData = taskwiseActualBudgetDatafun(from_date,to_date,user)
  
    return JsonResponse({'from_date':from_date,
                         'to_date':to_date,
                         'pieData':project_hour,
                        'totalWorkedHours':total_hrs,
                        'logs':timeSheet_logs,
                        'chartdata':chartdata,
                        'task_List':task_List,
                        'taskwiseActualBudgetData':taskwiseActualBudgetData})

def project_hours(from_date,to_date,user):

    project_hours=list(Submission.objects
                .values(quotation=F('assignId__quotation'),
                        projectName = F('assignId__quotation'))
                .filter(date__range=[from_date, to_date],assignId__assignTo = user)
                .order_by('quotation')
                .annotate(total_hrs = Sum('hours')))
    for i in project_hours:
        actualHour = float(secondToHours(i['total_hrs'])[:-3].replace(":","."))
        i['total_hrs'] = actualHour
    return project_hours

def taskwiseActualBudgetDatafun(from_date,to_date,user):

    task_list = list(Submission.objects
                .annotate(quotation=F('assignId__quotation'),
                        taskName = F('assignId__taskName'))
                .values('quotation','taskName')
                .filter(date__range=[from_date, to_date],assignId__assignTo = user)
                .exclude(assignId__quotation="Non project")
                .order_by('assignId__taskName')
                )
    if task_list:
        # Extract quotations and task names from task_list
        quotations, task_names = zip(*[(item['quotation'], item['taskName']) for item in task_list])

        task_hours=list(Submission.objects
                                    .filter(
                                        assignId__quotation__in=quotations,
                                        assignId__taskName__in=task_names
                                    )
                                    .exclude(assignId__quotation="Non project")
                                    .values(
                                        quotation=F('assignId__quotation'),
                                        taskName=F('assignId__taskName')
                                    )
                                    .annotate(
                                        act_hrs=Sum('hours'),
                                        assignId__count=Count('assignId', distinct=True)
                                    )
                                    .order_by('quotation'))
        args={'quotation_no__in':quotations}
        return getActualBudgetList(task_hours,args)
    return []

def getActualBudgetList(task_hours,args):
    args['create_date__gte'] = '2024-06-01'
    taskwisebudgetHrsData = list(Quotation.objects.using('erp').values('quotation_no',taskName=F('quotationcost__cost__name')).annotate(
            bdg_hrs=Sum(F('quotationcost__quantity')) * 9
        ).filter(**args).exclude(quotationcost__cost__name__isnull=True).order_by('quotation_no'))
    # Create a dictionary for quick lookup of budget hours by (quotation, taskName)
    bdg_dict = {(item['quotation_no'], item['taskName']): item['bdg_hrs'] for item in taskwisebudgetHrsData}

    # Merge the lists
    merged_list = []
    for item in task_hours:
        quotation = item['quotation']
        task_name = item['taskName']
        act_hrs = float(secondToHours(item['act_hrs'])[:-3].replace(":","."))
        emp_count = item['assignId__count']
        # Look up the corresponding budgeted hours from taskwisebudgetHrsData (if any)
        bdg_hrs = bdg_dict.get((quotation, task_name), 0)
        
        # Merge the actual and budgeted hours
        merged_item = {
            'quotation': quotation,
            'taskName': task_name,
            'act_hrs': act_hrs,
            'bdg_hrs': bdg_hrs,
            "emp_count":emp_count
        }
        merged_list.append(merged_item)

    # For tasks in taskwisebudgetHrsData that don't have a match in task_hours, add them to the merged list
    for item in taskwisebudgetHrsData:
        quotation = item['quotation_no']
        task_name = item['taskName']
        
        # Check if the task is already in merged_list
        if not any(x['quotation'] == quotation and x['taskName'] == task_name for x in merged_list):
            merged_item = {
                'quotation': quotation,
                'taskName': task_name,
                'act_hrs': 0,  # No actual hours available
                'bdg_hrs': item['bdg_hrs'],
                "emp_count": 0
            }
            merged_list.append(merged_item)
    return list(merged_list)

def overview_chart_data(from_date,to_date,user):
    # Adjusted query
    daily_hours = list(Submission.objects
        .filter(date__range=[from_date, to_date], assignId__assignTo = user)
        .annotate(hrs=ExpressionWrapper(F('hours') / 3600.0, output_field=FloatField()))
        .annotate(message=Case(
            When(assignId__quotation="Non project", then=Concat(Value("Others"), V(' '), F('assignId__taskName'), output_field=CharField())),
                default=Concat('assignId__quotation', V(' '), 'assignId__taskName', output_field=CharField()),
                output_field=CharField())
        )
        .values('date', 'message','hrs')  # Group by day and message (task + hours)
        .order_by('date')
        .annotate(total_hrs=Sum('hrs'))
    )

    # Organize data into the desired format
    result = []
    for entry in daily_hours:
        day = entry['date']
        message = entry['message']
        hrs = entry['hrs']
        
        # Check if the day already exists in the result list
        existing_day = next((item for item in result if item['day'] == day), None)
        
        if existing_day:
            # Add task hours to the corresponding day
            existing_day[message] = hrs
        else:
            # Create a new day entry if not found
            result.append({'day': day, message: hrs, 'none': 0})

    # Ensure 'none' is added to days that don't have any specific tasks
    for day_entry in result:
        if 'none' not in day_entry:
            day_entry['none'] = 0
    
    #Retrieve distinct task data (quotation + taskName)

    task_List =list(Submission.objects.values(quotation=F('assignId__quotation'),
                        taskName = F('assignId__taskName')).distinct())

    # Output result
    return result,task_List

def timesheet_daily_hours(from_date,to_date,user):
    total_hrs = Submission.objects.filter(date__range=[from_date, to_date],assignId__assignTo = user) .aggregate(hrs = Sum('hours')) 
    total_hrs['hrs'] =secondToHours(total_hrs['hrs'])[:-3]

    timeSheet_logs = list(Submission.objects           
                        .filter(date__range=[from_date, to_date],assignId__assignTo = user)  
                        .order_by('-date')
                        .annotate(quotation=F('assignId__quotation'),
                                # customerName=F('assignId__customerName'),
                                projectName=F('assignId__customprojectName'),
                                # assignBy=F('assignId__assignBy'),
                                # assignByName=F('assignId__assignBy__first_name'),
                                # project=F('assignId__project'),
                                # projectName=F('assignId__projectName'),
                                # milestone=F('assignId__milestone'),
                                milestoneName=F('assignId__milestoneName'),
                                # task=F('assignId__task'),
                                taskName=F('assignId__taskName'),
                                timesheet_status=F('status'),
                                total_hrs = Sum('hours')
                                )
                        .values('quotation',
                                'projectName',
                                'milestoneName',
                                'taskName',
                                'date',
                                'hours',
                                'id',
                                'rate',
                                "rejection_reason",
                                'timesheet_status'))
    for i in timeSheet_logs:
        i['hours'] = secondToHours(i['hours'])[:-3]
    return total_hrs,timeSheet_logs


# Summary
@csrf_protect
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def OverallTimesheetLog(request):
    if request.user.role != "Employee":

        from_date, to_date = get_default_date_range()

        pro_name = get_quotations()

        emp_name = get_employees()

        selectedEmployee = selectedProject = None
    
        args = {}

        args['date__range'] = [from_date, to_date]
        
        if request.method == 'POST':
            args, selectedEmployee, selectedProject, from_date, to_date = extract_post_filters(request, from_date, to_date)

        logs = Submission.objects.annotate(uid__first_name=F('assignId__assignTo__first_name'),
                                           quotation=F('assignId__quotation'),
                                           projectName =F('assignId__customprojectName'),
                                           milestoneName =F('assignId__milestoneName'),
                                           taskName =F('assignId__taskName'),
                                           timesheet_status =F('status')
                                           ).values('uid__first_name',
                                                    'date',
                                                    'quotation',
                                                    'projectName',
                                                    'milestoneName',
                                                    'taskName',
                                                    'rate',
                                                    'rejection_reason',
                                                    'timesheet_status',
                                                    'hours')\
                                        .filter(**args)\
                                        .annotate(rating = Case(When(rate=1, then=Value("Poor")),
                                                    When(rate=2, then=Value("Average")),
                                                    When(rate=3, then=Value("Good")),
                                                    When(rate=4, then=Value("Very Good")),
                                                    When(rate=5, then=Value("Excellent")),
                                                    default=Value(" "),
                                                    output_field=CharField(),
                                                ))\
                                        .order_by('date')   


        for i in logs:
            if i['quotation'] == "Non project":
                i['quotation'] = "Others"
                i['projectName'] = None
            i['hours'] = secondToHours( i['hours'])[:-3]

        return render(request,'overall_timsheet_log.html',{"module":"analysys",'logs':list(logs),
                                                           'from_date':from_date,''
                                                           'to_date':to_date,
                                                           'selectedProject':selectedProject,
                                                           'selectedEmpolyee':selectedEmployee,
                                                           'pro_name':pro_name,
                                                           'emp_name':emp_name})
    
    return HttpResponse("Sorry!! You are not Authorized")

# Task Analysis
@csrf_protect
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def task_analysis(request):
    from_date, to_date = get_default_date_range()
    employees = get_employees()
    quotations = get_quotations()
    selectedEmployee = selectedProject = None
    args = {}
    args['date__range'] = [from_date, to_date]
    if request.method == 'POST':
        args, selectedEmployee, selectedProject, from_date, to_date = extract_post_filters(request, from_date, to_date)
    
    data = Submission.objects.filter(**args)\
                                .annotate(taskName=F('assignId__taskName'),
                                            quotationName=F('assignId__quotation'))\
                                .values('taskName','quotationName')\
                                .annotate(total_hrs=Sum('hours'))\
                                .exclude(quotationName='Non project')\
                                .order_by('taskName')

    distinct_data = list(data.values('quotationName').distinct())

    result, task_name = [], None
    for item in data:
        task_name_temp = item["taskName"]
        try:
            total_hours = float(secondToHours(item['total_hrs'])[:-3].replace(":", "."))
        except Exception:
            total_hours = 0

        if result and task_name == task_name_temp:
            result[-1][item["quotationName"]] = total_hours
        else:
            result.append({
                "taskName": task_name_temp,
                item["quotationName"]: total_hours
            })
            task_name = task_name_temp

    return render(request, 'task_Analysis.html', {
                            "module": "analysys",
                            'data': result,
                            'from_date': from_date,
                            'to_date': to_date,
                            'selectedProject': selectedProject,
                            'selectedEmpolyee': selectedEmployee,
                            'emp_name': employees,
                            'quotations': quotations,
                            'series_data': distinct_data
                        })

# Project Analysis
@csrf_protect
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def allProjectAnalysis(request):
    from_date, to_date = get_default_date_range()
    employees = get_employees()
    quotations = get_quotations()

    selectedEmployee = selectedProject = None
    args = {}
    args['date__range'] = [from_date, to_date]
    if request.method == 'POST':
        args, selectedEmployee, selectedProject, from_date, to_date = extract_post_filters(request, from_date, to_date)

    data = list(Submission.objects
            .filter(**args)
            .annotate(uid__id=F('assignId__assignTo'),
                    projectName=F('assignId__customprojectName'),
                    quotation=F('assignId__quotation'))
            .values('uid__id', 
                    'projectName',
                    'quotation')
            .annotate(total_hrs=Sum('hours'))
            .exclude(quotation='Non project')
            .order_by('projectName'))

    result, pro_name = [], None
    for item in data:
        pro_name_temp = item["quotation"]
        try:
            total_hours = float(secondToHours(item['total_hrs'])[:-3].replace(":", "."))
        except Exception:
            total_hours = 0

        if result and pro_name == pro_name_temp:
            result[-1][item["uid__id"]] = total_hours
        else:
            result.append({
                "projectName":item['quotation'],# f"{item['quotation']} {item['projectName'] or ''}",
                item["uid__id"]: total_hours,
                "none": 0
            })
            pro_name = pro_name_temp

    return render(request, 'all-project-analysis.html', {
        "module": "analysys",
        'data': result,
        'from_date': from_date,
        'to_date': to_date,
        'selectedProject': selectedProject,
        'selectedEmployee': selectedEmployee,
        'employees': employees,
        'quotations': quotations
    })



def extract_post_filters(request, from_date, to_date):
    selectedEmployee = request.POST.get('Empid', '').strip()
    selectedProject = request.POST.get('project', '').strip()
    from_date = request.POST.get('from_date', from_date)
    to_date = request.POST.get('to_date', to_date)

    args = {}
    if selectedProject:
        args['assignId__quotation'] = selectedProject
    if selectedEmployee:
        args['assignId__assignTo'] = selectedEmployee
    args['date__range'] = [from_date, to_date]
    
    return args, selectedEmployee, selectedProject, from_date, to_date

def get_quotations(label_field='project__name', custom_label_field='assignId__customprojectName'):
    quotations = list(
                        Quotation.objects.using('erp')
                        .filter(
                            quotation_no__isnull=False,
                            customer_name__isnull=False
                        )
                        .annotate(project_label=Coalesce('custom_project_name', 'project__name'))
                        .values(
                            'quotation_no',
                            'customer_name',
                            label_field if label_field != 'project_label' else 'project_label'
                        )
                        .distinct()
                    )

    undefinedJobs = Submission.objects.values(
        quotation_no=F('assignId__quotation'),
        customer_name =F('assignId__customerName'),
        project__name=F(custom_label_field)
    ).filter(quotation_no__icontains='/UN/').distinct()

    return quotations + list(undefinedJobs)

def get_default_date_range():
    today = datetime.now()
    from_date = today.replace(day=1).strftime('%Y-%m-%d')
    to_date = today.strftime('%Y-%m-%d')
    return from_date, to_date

def get_employees():
    return list(users.objects.values('id', 'first_name').distinct().order_by('first_name'))



# Get Non Submitted Employees
@csrf_exempt
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getNonSubmittData(request):
    if request.method == 'POST':
        weekYear = request.POST.get('weekYear')
        weekNumber = request.POST.get('weekNum')
        status = request.POST.get('status', 'Submission')
        # get the week start date from week year and week number
        if weekYear and weekNumber:
            if status == 'Submission':
                try:
                    # Make sure weekNumber is two digits and minus 2 days to get the start date
                    week_start_date = datetime.strptime(f'{weekYear} {int(weekNumber):02d} 1', '%Y %W %w') - timedelta(days=2)
                    # Get all employees who have not submitted timesheets for the week
                    submitted_employees = TimesheetStatus.objects.filter(
                            Q(weekyear=weekYear,weeknumber=weekNumber) ,
                            Q(timesheet_status__in =['Submitted', 'Accepted', 'Rejected']) 
                    ).values_list('uid_id',flat=True).distinct()
                    # Filter employees who are active and not in the submitted list
                    employees = users.objects.filter(
                        Q(is_active=True),
                        ~Q(id__in=submitted_employees),
                    ).exclude(role__in=['Consultant', 'Admin', 'HR', 'CEO']).values('first_name').distinct()

                except ValueError as e:
                    print("Error parsing date:", e)
                    return JsonResponse({"error": "Invalid week year or week number."}, status=400)
            else:
                try:
                # Make sure weekNumber is two digits and minus 2 days to get the start date
                    week_start_date = datetime.strptime(f'{weekYear} {int(weekNumber):02d} 1', '%Y %W %w') - timedelta(days=2)
                    # Get all employees who have not approved timesheets for the week
                    employees = Submission.objects.filter(
                                    Q(date__range=[week_start_date, week_start_date + timedelta(days=6)]),
                                    Q(status='Submitted')
                                ).values(
                                    first_name=F('approvedBy__first_name')
                                ).distinct()
                except ValueError as e:
                    print("Error parsing date:", e)
                    return JsonResponse({"error": "Invalid week year or week number."}, status=400)

    return JsonResponse({"success": True, "employees": list(employees)}, status=200)

