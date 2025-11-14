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
from django.utils import timezone
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
    current_date = datetime.now()
    week_start_date = current_date - timedelta(days=current_date.weekday())
    current_weekyear = week_start_date.year
    current_week = int(week_start_date.strftime("%V"))

    selectedYear = current_weekyear
    selectedWeekStart = current_week - 8
    selectedWeekEnd = current_week
    selectedEmployee = ''

    employees = users.objects.annotate(
            joinedWeek=ExtractWeek('date_joined'),
            joinedYear=ExtractYear('date_joined'),
            resignedWeek=ExtractWeek('resigned_date'),
            resignedYear=ExtractYear('resigned_date')
        ).exclude(role__in=['Consultant', 'Admin', 'HR', 'CEO'])\
        .values('first_name', 'reporting_to', 'id', 'joinedWeek', 'joinedYear','resignedWeek','resignedYear').order_by('id')

    timesheetStatusDetails = TimesheetStatus.objects.annotate(
            submissionStatus=Coalesce(F('submission_status'), Value(False)),
            actionStatus=Coalesce(F('action_status'), Value(False)),
            timesheetStatus=F('timesheet_status'),
            weekNumber=F('weeknumber'),
            weekYear=Coalesce(F('weekyear'), Value(selectedYear))
        ).values(
            'submissionStatus', 'actionStatus', 'timesheetStatus', 
            'weekNumber', 'weekYear','uid'
        ).order_by('uid')

    if request.method == 'POST':
        selectedYear = int(request.POST.get('weekYear'))
        selectedWeekStart = int(request.POST.get('weekStart'))
        selectedWeekEnd = int(request.POST.get('weekEnd'))
        selectedEmployee = request.POST.get('emplyeeId')

    weekStartDate = datetime.fromisocalendar(selectedYear, selectedWeekStart, 1)
    weekEndDate = datetime.fromisocalendar(selectedYear, selectedWeekEnd, 7)
    # Fetch all submission data for selected week range in ONE query
    all_task_statuses = Submission.objects.filter(
        date__range=[weekStartDate, weekEndDate]
    ).select_related('assignId__assignTo').values(
        'assignId__assignTo', 'date', 'status', 'approved_status'
    )

    # Build a lookup dictionary for approval statuses
    task_status_lookup = defaultdict(list)
    for item in all_task_statuses:
        user_id = item['assignId__assignTo']
        date = item['date']
        week = date.isocalendar()[1]
        year = date.isocalendar()[0]
        key = (user_id, week, year)
        task_status_lookup[key].append({
            'status': item['status'],
            'approved_status': item['approved_status']
        })

    # Apply user/manager filters
    base_filter_timesheetStatus = {
        'weekyear': selectedYear,
        'weeknumber__in': list(range(selectedWeekStart, selectedWeekEnd + 1))
    }

    base_filter_users = {}
    if selectedEmployee:
        base_filter_users['id'] = selectedEmployee
    elif request.user.role not in ['Consultant', 'Admin', 'HR', 'CEO']:
        base_filter_users['reporting_to'] = request.user.id

    timesheetStatusDetails = timesheetStatusDetails.filter(**base_filter_timesheetStatus)
    employees = employees.filter(**base_filter_users)

    # Final result construction
    result = defaultdict(lambda: defaultdict(dict))
    for emp in employees:
        if timesheetStatusDetails:
            for item in timesheetStatusDetails:
                emp_id = emp['id']
                result[emp_id]['first_name'] = emp['first_name']
                result[emp_id]['joinedWeek'] = emp['joinedWeek']
                result[emp_id]['joinedYear'] = emp['joinedYear']
                result[emp_id]['resignedWeek'] = emp['resignedWeek']
                result[emp_id]['resignedYear'] = emp['resignedYear']

                if emp['id'] == item['uid']:
                    week_num = item['weekNumber'] 
                    week_yr = item['weekYear']
                    result[emp_id]['weekYear'] = week_yr
                    if week_num is not None:
                        approval_status = getApprovalStatusFromCache(task_status_lookup, emp_id, week_num, week_yr)

                    result[emp_id][week_num] = {
                        'action_status': item['actionStatus'],
                        'submission_status': item['submissionStatus'],
                        'timesheet_status': item['timesheetStatus'],
                        'approval_status': approval_status
                    }
        else:
            emp_id = emp['id']
            result[emp_id]['first_name'] = emp['first_name']
            result[emp_id]['joinedWeek'] = emp['joinedWeek']
            result[emp_id]['joinedYear'] = emp['joinedYear']
            result[emp_id]['resignedWeek'] = emp['resignedWeek']
            result[emp_id]['resignedYear'] = emp['resignedYear']
            week_num = None 

    return JsonResponse({
        "employees": dict(result),
        'year': current_weekyear,
        'current_week': current_week
    })

def getApprovalStatusFromCache(task_status_lookup, user_id, weeknumber, year):
    key = (user_id, weeknumber, year)
    task_items = task_status_lookup.get(key, [])

    if not task_items:
        return 'notsubmitted'

    statuses = [item['status'] for item in task_items]
    approved_statuses = [item['approved_status'] for item in task_items]

    if 'Rejected' in statuses or None in statuses:
        return 'notsubmitted'

    if len(set(statuses)) == 1 and statuses[0] == 'Accepted':
        return 'ontime' if 1 in approved_statuses else 'delayedapproval'

    if all(s != 'Accepted' for s in statuses):
        return 'approvalpending'

    return 'missed'

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
                week_start_date = datetime.fromisocalendar(int(weekYear), int(weekNumber), 1)
                #  get all approved details  of employee for the week
                timesheetstatus = Submission.objects.filter(assignId__assignTo = empId,
                                                    date__range =[week_start_date, week_start_date + timedelta(days=6)]
                                                    )\
                                                    .annotate(
                                                        approvedStatus=Case(
                                                            When(status='Submitted', then=Value('Pending')),
                                                            When(approved_status=True, then=Value('Accepted Ontime')),
                                                            default=Value('Accepted Delayed'),
                                                            output_field=CharField()
                                                        ),
                                                        approvedBy__first_name=F('assignId__assignBy__first_name')
                                                    )\
                                                    .values(
                                                        'approvedStatus',
                                                        # 'status',
                                                        approvedBy__first_name = F('assignId__assignBy__first_name'))\
                                                    .distinct()
                                                    # .annotate(updated_date_only=TruncDate('updated_date'))\
            except ValueError as e:
                print("Error parsing date:", e)
                return JsonResponse({"error": "Invalid week year or week number."}, status=400)
    return JsonResponse({"success":True ,"timesheetstatus": list(timesheetstatus)},status =200)   
        
@csrf_exempt
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getNonSubmittData(request):
    if request.method == 'POST':
        selectedWeekYear = int(request.POST.get('weekYear'))
        weekStart = int(request.POST.get('weekStart'))
        weekEnd = int(request.POST.get('weekEnd'))
        # employee = int(request.POST.get('emplyeeId'))
        approvalList = {}
        week_start_date = datetime.fromisocalendar(selectedWeekYear, int(weekStart), 1)
        week_end_date = datetime.fromisocalendar(selectedWeekYear, int(weekEnd), 7)
        
        approval_status = Submission.objects.filter(
            date__range=[week_start_date, week_end_date]
        ).values('approvedBy__first_name','date','approvedBy','approved_status','status')
        for i in range(weekStart,weekEnd+1):
            week_start_date_ = datetime.fromisocalendar(selectedWeekYear, int(i), 1)
            data = list(approval_status.filter(date__range=[week_start_date_, week_start_date_+ timedelta(days=6)])
                .values('approvedBy__first_name','approvedBy')
                .annotate(
                    submitted_count = Count('approvedBy', filter=Q(status='Submitted')),
                    joinedWeek=ExtractWeek('approvedBy__date_joined'),
                    joinedYear=ExtractYear('approvedBy__date_joined')
                ).order_by('approvedBy__first_name'))
            approvalList[i] = data
        for week_number, approvals in approvalList.items():
            week_start_date_ = datetime.fromisocalendar(selectedWeekYear, int(week_number), 1)
            # week_start_date_ = datetime.strptime(f'{selectedWeekYear} {int(week_number):02d} 1', '%Y %W %w')
            for item in approvals:
                if item['submitted_count'] != 0:
                    item['timesheetstatus'] = 'Pending'
                else:
                    item['timesheetstatus'] = ''
        return JsonResponse({"approvalData":approvalList})

@csrf_exempt
@login_required(login_url='home')
@unathenticated
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getConsolidatedReportData(request):
    consolidatedData=[]
    if request.method == 'POST':
        weekStart = int(request.POST.get('weekStart'))
        weekEnd = int(request.POST.get('weekEnd'))
        selectedWeekYear = int(request.POST.get('weekYear'))
        statusType = request.POST.get('status')
        if statusType == 'submission_status':

            data = users.objects.exclude(role__in=['Consultant', 'Admin', 'HR', 'CEO']).annotate(
                joinedWeek=ExtractWeek('date_joined'),
                joinedYear=ExtractYear('date_joined'),
                resignedWeek=ExtractWeek('resigned_date'),
                resignedYear=ExtractYear('resigned_date'),

                submittedCount=Count(
                    'timesheetstatus',
                    filter=Q(
                        timesheetstatus__timesheet_status__in=['Submitted', 'Rejected', 'Accepted'],
                        timesheetstatus__weekyear=selectedWeekYear,
                        timesheetstatus__weeknumber__range=(weekStart, weekEnd)
                    ),
                    distinct=True
                ),

                ontimecount=Count(
                    'timesheetstatus',
                    filter=Q(
                        timesheetstatus__timesheet_status__in=['Submitted', 'Rejected', 'Accepted'],
                        timesheetstatus__weekyear=selectedWeekYear,
                        timesheetstatus__weeknumber__range=(weekStart, weekEnd),
                        timesheetstatus__submission_status=True
                    ),
                    distinct=True
                )
            ).values(
                'id', 'first_name', 'joinedWeek', 'joinedYear', 'resignedWeek', 'resignedYear',
                'submittedCount', 'ontimecount'
            ).order_by('first_name')

            consolidatedData=list(data)
        else:

           # Get the full date range of the selected weeks
            week_start_date = datetime.fromisocalendar(selectedWeekYear, int(weekStart), 1)
            week_end_date = datetime.fromisocalendar(selectedWeekYear, int(weekEnd), 7)

            # Pre-filter submissions in the overall date range to avoid querying the DB repeatedly
            approval_status = Submission.objects.filter(
                date__range=[week_start_date, week_end_date]
                ).values(
                    'approvedBy__first_name', 'date', 'approvedBy', 'approved_status', 'status'
                ).exclude(approvedBy__role__in=['Consultant', 'Admin', 'HR', 'CEO']).annotate(
                    joinedWeek = ExtractWeek('approvedBy__date_joined'),
                    joinedYear = ExtractYear('approvedBy__date_joined'),
                    resignedWeek = ExtractWeek('approvedBy__resigned_date'),
                    resignedYear = ExtractYear('approvedBy__resigned_date'))\
                .order_by('approvedBy__first_name')
            
            approvalList = defaultdict(lambda: {
                'notApproved_count': 0,
                'ontimeApproved_count': 0,
                'delayedApproved_count': 0
            })

            # Loop through each week in the selected range
            for i in range(weekStart, weekEnd + 1):
                week_start_date_ = datetime.fromisocalendar(selectedWeekYear, int(i), 1)
                week_end_date_ = week_start_date_ + timedelta(days=6)
                # Filter data for the week
                weekly_data = list(approval_status.filter(
                    date__range=[week_start_date_, week_end_date_],
                ).values('approvedBy__first_name', 'approvedBy','joinedWeek','joinedYear','resignedWeek','resignedYear').annotate(
                    submitted_count=Count('approvedBy', filter=Q(status='Submitted')),
                    ontimeApproval_count=Count('approvedBy', filter=Q(status__in=['Accepted', 'Rejected'], approved_status=1)),
                    delayedApproval_count=Count('approvedBy', filter=Q(status__in=['Accepted', 'Rejected'], approved_status=0)),
                ))

                # Update approval counts
                for item in weekly_data:
                    name = item['approvedBy__first_name']
                    if item['submitted_count']:
                        approvalList[name]['notApproved_count'] += 1
                    if item['ontimeApproval_count']:
                        approvalList[name]['ontimeApproved_count'] += 1
                    if item['delayedApproval_count']:
                        approvalList[name]['delayedApproved_count'] += 1
                    approvalList[name]['joinedWeek'] = item['joinedWeek']
                    approvalList[name]['joinedYear'] = item['joinedYear']
                    approvalList[name]['resignedWeek'] = item['resignedWeek']
                    approvalList[name]['resignedYear'] = item['resignedYear']
            consolidatedData = dict(approvalList)
    return JsonResponse({"ConsolidatedSubmittedReport":consolidatedData})

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
                                            ).distinct() #.exclude(budget=0 )
    
    if request.method == 'POST': 
        quotationNum = request.POST.get('quotationNum')
        task_list=list(Submission.objects
                .values(quotation=F('assignId__quotation'),
                        taskName=F('assignId__taskName'))
                .filter(quotation = quotationNum)
                .annotate(act_hrs = Sum('hours'))
                .annotate(Count('assignId',distinct=True))
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

        i['delta'] = round(i['actual'] - i['budget'] ,2)  # Difference
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
      
    total_hrs,timeSheet_logs,project_hour,task_List,chartdata = timesheet_daily_hours(from_date,to_date,user)
  
    return JsonResponse({'from_date':from_date,
                         'to_date':to_date,
                         'pieData':project_hour,
                        'totalWorkedHours':total_hrs,
                        'logs':timeSheet_logs,
                        'chartdata':chartdata,
                        'task_List':task_List})
                        # 'taskwiseActualBudgetData':taskwiseActualBudgetData

@csrf_exempt
def taskwiseActualBudgetDatafun(request):
    if request.method =='POST':
        from_date =request.POST['from_date']
        to_date  =request.POST['to_date']
        user = request.user
    print(from_date,to_date,user)
    # from_date,to_date,user
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
        return JsonResponse({"data":getActualBudgetList(task_hours,args)})
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

def timesheet_daily_hours(from_date,to_date,user):
    total_hrs = {} 

    timeSheet_logs = list(Submission.objects           
                        .filter(date__range=[from_date, to_date],assignId__assignTo = user)  
                        .order_by('-date')
                        .annotate(quotation=F('assignId__quotation'),
                                projectName=F('assignId__customprojectName'),
                                assignBy=F('approvedBy__first_name'),
                                milestoneName=F('assignId__milestoneName'),
                                taskName=F('assignId__taskName'),
                                timesheet_status=F('status')
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
                                'timesheet_status',
                                'assignBy'))
    total = 0
    project_hrs = {}
    dailyHours = {}
    tasks = set()
    for i in timeSheet_logs:
# ----------------------------project status------------
        quotation = i['quotation']
        project_name = i['projectName']
        task_name = i['taskName']
        if quotation not in project_hrs:
            project_hrs[quotation] ={
                                "quotation" : quotation,
                                "projectName" : project_name,
                                "total_hrs" : 0
                                }
        project_hrs[quotation]['total_hrs'] += float(secondToHours(i['hours'])[:-3])
        
# ---------------------daily status-------------------------------------------
        date_ = i['date']
        mergeTaskName = quotation +" "+ task_name
        if date_ not in dailyHours:
            dailyHours[date_]={
                "day":date_,
                mergeTaskName:round(i['hours'] / 3600.0,2),
                "none":0
            }
        else:
            dailyHours[date_][mergeTaskName] = round(i['hours'] / 3600.0,2)

        tasks.add(mergeTaskName)

# =======================================================================

        total += i['hours']
        i['hours'] = secondToHours(i['hours'])[:-3]
       
    total_hrs['hrs'] = secondToHours(total)[:-3]
    task_list = list(tasks)
    return total_hrs,timeSheet_logs,list(project_hrs.values()),task_list,list(dailyHours.values())


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

    # Extract distinct quotation names without new DB query
    distinct_data = [
        {'quotationName': q}
        for q in {item['quotationName'] for item in data}
    ]

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




