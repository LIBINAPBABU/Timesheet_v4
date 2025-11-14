from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import connection, transaction,DatabaseError,IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import (
    Case,
    CharField,
    F,
    Max,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, csrf_protect

import pandas as pd
import json
import re
# Custom decorators
from Employee.decorators import allowedGroups, unathenticated

# Models
from Employee.models import users
from Settings.models import  CostMaster, Task, phaseCategory
from .models import (
    # AssignedMilestone,
    AssignedQuotation,
    AssignedTask,
    Submission,
    Quotation,
    TimesheetStatus,
    # TimesheetSubmission,
    Customer
)

# Email templates
from templates.mailContents import rejectedEmailBody,lockedEmailBody, submitedEmailBody, dailyReminderMessageBodyForHr,UnlockApprovedEmailBody
import logging

# Set up the logger (you can configure it further in your settings.py)
logger = logging.getLogger(__name__)
#------------------------------- timesheeet ----------------------------------------

# Create your views here.
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def submission(request):
    return render(request,'submission.html',{"module":"timesheet"})

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_exempt
def submission_templete(request):
    # Get the current date and time
    current_date = datetime.today()

    week_start_date = current_date - timedelta(days=current_date.weekday())
    # Handle POST requests to process different modes
    if request.method == 'POST':
        # Get the start date of the current week from the form submission
        present_week_start_date = datetime.strptime(request.POST.get('fromDate'),'%d-%b-%Y')
        # Get the mode from the form submission (e.g., predate, postdate, etc.)
        mode = request.POST.get('mode')
        # Set the initial week start date based on the form submission
        week_start_date = present_week_start_date
        # Process different modes accordingly
        if mode == 'predate':
            # Move the week start date one week back
            week_start_date = present_week_start_date - timedelta(days=7)
        elif mode =='postdate':
            # Move the week start date one week forward
            week_start_date = present_week_start_date + timedelta(days=7)
        elif mode == "assignproject":
            # Assign a project to the user
            handle_assign_project(request.user, request.POST.get('ids'), week_start_date)
        elif mode == "fetchAssignTaskData":
            # fetch Assign tasks list to the user for the given week
            return fetch_projects(request,week_start_date)
        elif mode == "assignmilestone":
            # Assign milestones to the user for the given week
            handle_assign_tasks(request.user, json.loads(request.POST.get('checkedItems')), present_week_start_date)
        elif mode == 'removemilestone':
            # Attempt to remove a milestone, and return an error if it fails
            if not handle_remove_assign_task(request.user, request.POST, present_week_start_date):
                return JsonResponse({'status': "Can't remove. You need to remove hours from the task first!"})
        elif mode == "duplicate":
            # Duplicate milestones for the user in the current week
            handle_duplicate_assign_tasks(request.user, present_week_start_date)
        elif mode == "submit":
            Comments = request.POST.get('Comments')
            # Submit the user's timesheet for the current week
            handle_submission(request.user, present_week_start_date, current_date, Comments)
        elif mode == "rejectionReason": 
            # Handle and return rejection reasons for the user's timesheet
            return handle_rejection_reasons(request.user, present_week_start_date)
        else:
            # Update the timesheet and check if the update is valid
            result = update_timesheet(request)
            if result['status'] != "valid":
                # Return an error message if the timesheet update is not valid
                return JsonResponse (result)
    # Calculate the end date of the current week
    week_end_date = week_start_date + timedelta(days=6)
    # Prepare the context data to be returned in the response
    context = prepare_context_task_data(request.user, week_start_date, week_end_date, current_date)
    # Return the context data as a JSON response
    return JsonResponse(context)

# (job no: fetch data)
def fetch_quotations(request):
    try:
        # Get the latest quotation id for each quotation_no .filter(create_date__gte ='2024-06-01')\
        quotation_ids = Quotation.objects.using('erp') \
            .filter(quotation_no__isnull=False,
                     customer_name__isnull =False) \
            .values('quotation_no') \
            .annotate(latest_id=Max('id')) \
            .values_list('latest_id', flat=True)

        customer_code_subquery = Customer.objects.filter(
                name=OuterRef('customer_name')
            ).values('code')[:1]

        project_list =  Quotation.objects.using('erp') \
            .filter(Q(id__in=quotation_ids)) \
            .select_related('project') \
            .annotate(customer_code=Subquery(customer_code_subquery)) \
            .values('quotation_no', 'project__name', 'custom_project_name','system_name',
                    'customer_name', 'id', 'sale_type', 'status', 'customer_code','quote_date') \
            .order_by('-id')

        assigned_projects = AssignedQuotation.objects.filter(user=request.user.id).values('quotation')

        return JsonResponse({"projectslist":list(project_list),"assignedProjectList":list(assigned_projects)})
    
    except DatabaseError as db_error:
        # Log database errors
        logger.error("Database error while fetching quotations for user %s: %s", request.user.id, db_error)
        return JsonResponse({"error": f"Database error: {str(db_error)}"}, status=500)

    except ObjectDoesNotExist as e:
        # Log missing object errors
        logger.error("Object not found for user %s: %s", request.user.id, e)
        return JsonResponse({"error": f"Object not found: {str(e)}"}, status=404)

    except Exception as e:
        # Log unexpected errors
        logger.critical("Unexpected error while fetching quotations for user %s: %s", request.user.id, e, exc_info=True)
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)

# Get project's and milestones for assigned milestone modal(undefined taskbutton fetch data)
def fetch_projects(request,weekStartDate):
    try:
        weekEndDate = weekStartDate+timedelta(days=6)
        selectedquotations = list(AssignedTask.objects.values('quotation','project','projectName','customerName','customprojectName','customerCode','systemName','quoted_date')
                                  .filter(assignTo=request.user,end_date__gte = weekStartDate,start_date__lte = weekEndDate)
                                  .exclude(quotation = "Non project").distinct())
        
        phaseCategoryData = list(phaseCategory.objects.values('category','phases','phases__name').order_by('phases'))
        
        # Create a dictionary to store results by phaseid
        resultDict = defaultdict(lambda: {'phaseid': None, 'phasename': None, 'categorys': []})

        # Populate the resultDict with the data
        for entry in phaseCategoryData:
            phaseid = entry['phases']
            phasename = entry['phases__name']
            category = entry['category']
            
            # Initialize phaseid entry if not yet initialized
            if resultDict[phaseid]['phaseid'] is None:
                resultDict[phaseid]['phaseid'] = phaseid
                resultDict[phaseid]['phasename'] = phasename
            
            # Append the category to the category list (avoiding duplicates)
            if category not in resultDict[phaseid]['categorys']:
                resultDict[phaseid]['categorys'].append(category)

        # Convert resultDict to a list
        phaseCategoryData = list(resultDict.values())

        # Fetch tasks with their associated milestones
        milestoneslist = list(
            CostMaster.objects.using('erp')
            .select_related('cost_category')  # Ensures we fetch related CostCategory data in one query
            .values(
                'id', 
                'name', 
                'cost_category__id', 
                'cost_category__name'
            )
        )

        # Group tasks by milestone
        milestone_dict = defaultdict(list)
        for item in milestoneslist:
            milestone_dict[(item['cost_category__id'], item['cost_category__name'])].append({
                'task': item['id'],
                'taskName': item['name']
            })

        # Build milestones list
        milestones = [
            {
                'milestone': milestone_id,
                'milestoneName': milestone_name,
                'tasks': tasks
            }
            for (milestone_id, milestone_name), tasks in milestone_dict.items()
        ]

        # Construct tree data
        tree_data = [
            {
                'quotation': item['quotation'],
                'customerName':item['customerName'],
                'customprojectName':item['customprojectName'],
                'customerCode':item['customerCode'],
                'systemName':item['systemName'],
                'project': item['project'],
                'projectName': item['projectName'],
                'milestones': milestones,
                'quoted_date': item['quoted_date']
            }
            for item in selectedquotations
        ]
        
        logger.info(f"Successfully fetched projects for user {request.user.id} in the week starting {weekStartDate}")
        return JsonResponse({'projects': tree_data,'phaseCategoryData':phaseCategoryData}, safe=False)
    except DatabaseError as db_error:
        # Log database errors
        logger.error("Database error while fetching quotations for user %s: %s", request.user.id, db_error)
        return JsonResponse({"error": f"Database error: {str(db_error)}"}, status=500)

    except ObjectDoesNotExist as e:
        # Log missing object errors
        logger.error("Object not found for user %s: %s", request.user.id, e)
        return JsonResponse({"error": f"Object not found: {str(e)}"}, status=404)

    except Exception as e:
        # Log unexpected errors
        logger.critical("Unexpected error while fetching quotations for user %s: %s", request.user.id, e, exc_info=True)
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)

def handle_assign_project(user, quotations, weekStartDate):
    try:
        # Load project IDs from JSON string
        try:
            quotations = json.loads(quotations)
            logger.info(f"Successfully loaded quotations: {quotations}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing quotations JSON: {e}")
            raise ValueError("Invalid JSON format for quotations.") from e
        
        # Retrieve quotation details
        try:
            logger.info(f"Fetching quotation details for quotations: {quotations}")

            customer_code_subquery = Customer.objects.filter(
                name=OuterRef('customer_name')
            ).values('code')[:1]

            quotationDetails = list(Quotation.objects.using('erp').annotate(
                    quotation_=F('quotation_no'),
                    customerName =F('customer_name'),
                    customprojectName =F('custom_project_name'),
                    systemName =F('system_name'),
                    customerCode =Subquery(customer_code_subquery),
                    projectName =F('project__name'),  # Renaming cost_category → milestone
                    milestone=F('quotationcost__cost__cost_category'),  # Renaming cost_category → milestone
                    milestoneName=F('quotationcost__cost__cost_category__name'),  # Renaming cost_category__name → milestone_name
                    task=F('quotationcost__cost'),  # Renaming cost → task
                    taskName=F('quotationcost__cost__name'),  # Renaming cost_name → task_name
                    quotedDate = F('quote_date')
            ).values(
                'quotation_', 
                'customerName',
                'customprojectName',
                'systemName',
                'customerCode',
                'project', 
                'projectName',
                'milestone',
                'milestoneName',
                'task',
                'taskName',
                'quotedDate'
            ).filter(id__in = quotations).distinct())

            # logger.info(f"Successfully fetched quotation details: {quotationDetails}")
        except DatabaseError as e:
            logger.error(f"Error fetching quotation details from ERP database: {e}")
            raise DatabaseError("Failed to fetch quotation details.") from e
        # Assign miliestone/Task to user
        handle_assign_tasks(user, quotationDetails, weekStartDate)
    except Exception as e:
        logger.error(f"An unexpected error occurred while assigning project: {e}")
        raise e  # Reraise the error after logging it

# New Tasks based Assigned by
def handle_assign_tasks(user, quotationDetails, start_date):
    try:
        logger.info(f"Starting to handle milestone assignment for user: {user.id} on {start_date}")
        # Prepare a list to hold new assignments
        assignments = []
        
        query = Q()

        for item in quotationDetails:
            query |= Q(
                quotation=item['quotation_'],
                customerName=item['customerName'],
                customprojectName=item['customprojectName'],
                systemName=item['systemName'],
                customerCode=item['customerCode'],
                # quoted_date=item['quotedDate'],
                milestone=item['milestone'],
                milestoneName=item['milestoneName'],
                task=item['task'],
                taskName=item['taskName'],
                assignTo=user
            )

        # Now run the query
        existing_tasks = AssignedTask.objects.filter(query).values(
            'id',
            'quotation',
            'customerName',
            'customprojectName',
            'systemName',
            'customerCode',
            'project', 
            'projectName',
            'milestone', 
            'milestoneName',
            'task',
            'taskName',
            'start_date',
            'end_date'
        )
        # Create a mapping for existing assigned tasks
        assigned_tasks_map = {
            (task['quotation'], task['project'], task['projectName'], task['milestone'], task['milestoneName'], task['task'], task['taskName'],task['customerName'], task['customprojectName'], task['systemName'], task['customerCode']): task
            for task in existing_tasks
        }
        # Prepare updates and new assignments
        updates = []
        for item in quotationDetails:
            key = (item['quotation_'],item['project'], item['projectName'],item['milestone'], item['milestoneName'], item['task'], item['taskName'],item['customerName'], item['customprojectName'], item['systemName'], item['customerCode'])
            assigned_task = assigned_tasks_map.get(key)
            if assigned_task:
                if assigned_task['start_date'] > start_date.date():
                    updates.append((item['quotation_'],item['project'], item['projectName'],item['milestone'], item['milestoneName'], item['task'], item['taskName'],item['customerName'], item['customprojectName'], item['systemName'], item['customerCode'], start_date, None))
                else:
                    updates.append((item['quotation_'],item['project'], item['projectName'],item['milestone'], item['milestoneName'], item['task'], item['taskName'],item['customerName'], item['customprojectName'], item['systemName'], item['customerCode'], None, start_date + timedelta(days=6)))
            else:
                nullMilestoneTask = AssignedTask.objects.filter(quotation=item['quotation_'],milestone=None,milestoneName=None,task=None,taskName=None).filter(assignTo = user).first()
                if nullMilestoneTask:
                    nullMilestoneTask.milestone = item['milestone']
                    nullMilestoneTask.milestoneName = item['milestoneName']
                    nullMilestoneTask.task = item['task']
                    nullMilestoneTask.taskName = item['taskName']
                    if nullMilestoneTask.start_date > start_date.date():
                        nullMilestoneTask.start_date = start_date
                    else:
                        nullMilestoneTask.end_date = start_date + timedelta(days=6)
                    nullMilestoneTask.save()
                else:
                    assignments.append(AssignedTask(
                        quotation=item['quotation_'],
                        customerName =item['customerName'], 
                        customprojectName =item['customprojectName'], 
                        systemName = item['systemName'], 
                        customerCode = item['customerCode'],
                        quoted_date = item['quotedDate'],
                        project=item['project'],
                        projectName=item['projectName'],
                        milestone=item['milestone'],
                        milestoneName=item['milestoneName'],
                        task=item['task'],
                        taskName=item['taskName'],
                        assignTo=user,
                        assignBy= user.reporting_to,
                        start_date=start_date,
                        end_date=start_date + timedelta(days=6)
                    ))
        # Bulk create new assignments
        if assignments:
            logger.info(f"Bulk creating {len(assignments)} new task assignments for user: {user.first_name}")
            try:
                AssignedTask.objects.bulk_create(assignments)
                logger.info(f"Successfully created new task assignments for user: {user.first_name}")
            except IntegrityError as e:
                logger.error(f"Integrity error while bulk creating task assignments: {e}")
                raise DatabaseError("Failed to create new task assignments due to integrity issues.") from e
            except DatabaseError as e:
                logger.error(f"Database error while bulk creating task assignments: {e}")
                raise DatabaseError("Failed to create new task assignments.") from e

        # Apply updates if any
        if updates:
            logger.info(f"Applying {len(updates)} updates to existing task assignments for user: {user.first_name}")
            try:
                for quotation_no,project, projectName,milestone, milestoneName, task, taskName,customerName,customprojectName,systemName,customerCode, start, end in updates:
                    update_data = {}
                    if start is not None:
                        update_data['start_date'] = start
                    if end is not None:
                        update_data['end_date'] = end
                    AssignedTask.objects.filter(
                        quotation=quotation_no,
                        customerName=customerName,
                        customprojectName=customprojectName,
                        systemName =systemName,
                        customerCode =customerCode,
                        project = project,
                        projectName=projectName,
                        milestone = milestone,
                        milestoneName=milestoneName,
                        task=task,
                        taskName=taskName,
                        assignTo=user,
                    ).update(**update_data)
            except IntegrityError as e:
                logger.error(f"Integrity error while updating task assignments: {e}")
                raise DatabaseError("Failed to update task assignments due to integrity issues.") from e
            except DatabaseError as e:
                logger.error(f"Database error while updating task assignments: {e}")
                raise DatabaseError("Failed to update task assignments.") from e
    except Exception as e:
        logger.error(f"An unexpected error occurred while handling task assignments for user: {user.first_name}: {e}")
        raise e  # Reraise the error after logging it

def prepare_context_task_data(user, start_date, end_date, current_date):
    #     # ......................timesheet table data
        try:
            table_header = [d.strftime('%a-%d') for d in pd.date_range(start_date, periods=7)] + ['Total']
            # logger.info(f"Generated table header: {table_header}")
        except Exception as e:
            logger.error(f"Error generating table header for user {user.id}: {e}")
            raise

        # Get assigned milestones for the user
        try:
            assigned_task = AssignedTask.objects.filter(
                        assignTo=user,
                        end_date__gte=start_date,
                        start_date__lte=end_date
                    ).values(
                        'quotation',
                        'customerName',
                        'customprojectName',
                        'systemName',
                        'customerCode',
                        'project',
                        'projectName',
                        'milestone',
                        'milestoneName',
                        'task',
                        'taskName',
                        'assignBy',
                        asignedId=F('id')
                    ).exclude(quotation="Non project")
            # logger.info(f"Fetched {len(assigned_task)} assigned milestones for user {user.id}")
        except DatabaseError as e:
            logger.error(f"Error fetching assigned milestones for user {user.id}: {e}")
            raise
        
        # Non_project table data
        try:
            non_project_milestones = Task.objects.annotate(
                milestoneName=F('mid__name'),
                milestone=F('mid__id'),
                taskName=F('name'),
                task=F('id'),
                quotation=Value('Non project'),
                customerName =Value('ICPro'), 
                customprojectName =Value('ICPro'), 
                systemName = Value('ICPro'), 
                customerCode = Value('ICPro'),
                project=Value(14),
                projectName=Value('Non project'),
                asignedId=Value(0),
                assignBy=Value(0)
            ).values('milestoneName', 'milestone', 'quotation', 'projectName','project','taskName','task','asignedId','customerName','customprojectName','systemName','customerCode','assignBy').order_by('taskName')
            # logger.info(f"Fetched {len(non_project_milestones)} non-project milestones")
        except DatabaseError as e:
            logger.error(f"Error fetching non-project milestones: {e}")
            raise
        
        assigned_list = list(assigned_task) + list(non_project_milestones)
        try:
            submitted_hours = Submission.objects.filter(date__range=[start_date, end_date],
                                                    assignId__assignTo=user
                    ).annotate( quotation=F('assignId__quotation'),
                                project=F('assignId__project'),
                                projectName=F('assignId__projectName'),
                                milestone=F('assignId__milestone'),
                                milestoneName=F('assignId__milestoneName'),
                                task=F('assignId__task'),
                                taskName=F('assignId__taskName'),
                                total_hrs=Sum('hours')).values('date','assignId', 'quotation', 'project',
                                                                'projectName', 'milestone', 
                                                                'milestoneName', 'task', 'total_hrs',
                                                                'taskName')
        except DatabaseError as e:
            logger.error(f"Error fetching submitted hours for user {user.id}: {e}")
            raise
        
        # Calculate project worked hours
        try:
            project_hours_dict, weekDaysHrs = calculate_project_worked_hours(submitted_hours)
        except Exception as e:
            logger.error(f"Error calculating project worked hours for user {user.id}: {e}")
            raise

        # Status
        try:
            timesheet_status = TimesheetStatus.objects.get(
                weekyear = start_date.year,
                weeknumber=start_date.strftime("%V"),
                uid=user)
            
            weekTimesheetStatus = timesheet_status.timesheet_status
            weekComments = timesheet_status.comments

            logger.info(f"Fetched {len(weekTimesheetStatus)} timesheet statuses for user {user.id} for week {start_date.strftime('%V')}")
        except TimesheetStatus.DoesNotExist:
            weekTimesheetStatus = None  # or set default status like 'Not Found'
            weekComments = None
        except DatabaseError as e:
            logger.error(f"Error fetching timesheet statuses for user {user.id}: {e}")
            raise

        # Handle timesheet data
        try:
            timesheet_data,noTaskQuotation = handle_Timesheet_data(assigned_list, project_hours_dict, start_date, submitted_hours)
        except Exception as e:
            logger.error(f"Error processing timesheet data for user {user.id}: {e}")
            raise
        
        non_project = [timesheet_data.pop('Non project', None)]
        
        # Calculate week day hours
        try:
            week_day_hours = append_default_actual_worked_hours(weekDaysHrs, start_date)
        except Exception as e:
            logger.error(f"Error appending default actual worked hours for user {user.id}: {e}")
            raise

        # Get actual hours
        try:
            actual_hours = Submission.objects.filter(
                    date__range=[start_date, end_date],
                    assignId__assignTo=user
                ).aggregate(total_hrs=Sum('hours'))
        except DatabaseError as e:
            logger.error(f"Error fetching actual hours for user {user.id}: {e}")
            raise
        try:
            Assigners =list(users.objects.values('first_name','id').filter(Q(is_active=True) & Q(role__in =["Lead","Manager","CEO"])).exclude(id= user.id).order_by('first_name'))
        except Exception as e:
            logger.error(f"Error Fetch User {user.id}: {e}")
        # Calculate estimated hours
        try:
            estimated_hours = calculate_estimated_hours(start_date)
        except Exception as e:
            logger.error(f"Error calculating estimated hours for user {user.id}: {e}")
            raise
        
        return {"currentdate": current_date.strftime('%d-%b-%Y'),
                "currentWeek": start_date.strftime("%V"),
                "from_date": start_date.strftime('%d-%b-%Y'),
                "to_date": end_date.strftime('%d-%b-%Y'),
                "tableHeader": table_header,
                "projectData": timesheet_data,
                "nonProjectdata": non_project,
                "weekDayHrs": list(week_day_hours.values()),
                "actual_hrs": actual_hours['total_hrs'],
                "estimated_hrs": estimated_hours,
                "timesheetStatus": weekTimesheetStatus,
                'weekComments':weekComments,
                "noTaskQuotation":noTaskQuotation,
                "assigners":Assigners}

#------------------------------
def calculate_estimated_hours(start_date):
    estimated_hrs=54.00
    day = int(datetime.strftime(start_date+timedelta(days=5),'%e').strip())
    if (8 <= day and day < 15) or (22 <= day and day < 29):
        estimated_hrs=45.00
    return "{:.2f}".format(estimated_hrs)

def calculate_project_worked_hours(submissionData):
    weekDaysHrs = {}
    projectHours = defaultdict(lambda: defaultdict(int))
    for task in submissionData:
        if task['date'].strftime('%d-%m-%Y') in weekDaysHrs:
            weekDaysHrs[task['date'].strftime('%d-%m-%Y')] += task['total_hrs']
        else:
            weekDaysHrs[task['date'].strftime('%d-%m-%Y')] = task['total_hrs']
        
        quotationId = task['quotation']
        date_str = task['date'].strftime('%d-%m-%Y')
        projectHours[quotationId][date_str] += task['total_hrs']
    projectHoursDict = {
            quotationId: {date: hours for date, hours in worked_hours.items()}
        for quotationId, worked_hours in projectHours.items()
    }
    return projectHoursDict,weekDaysHrs

def handle_Timesheet_data(data, projectHoursDict, startDate, submissionData): 
    # Calculate worked hours for milestones and tasks once and reuse
    noTaskQuotation = {}
    grouped_data = {}
    # Process each data item
    for item in data: 
        quotationId = item["quotation"]
        customerName =item['customerName'], 
        customprojectName =item['customprojectName'], 
        systemName = item['systemName'], 
        customerCode = item['customerCode'],
        projectId = item["project"]
        projectName = item["projectName"]
        milestoneId = item["milestone"]
        milestoneName = item["milestoneName"]
        taskID = item["task"]
        taskName = item["taskName"]
        asignedId = item["asignedId"]
        assignBy =item["assignBy"]
        
        milestone_worked_hours = calculate_milestone_worked_hour(submissionData.filter(quotation=quotationId))
        task_worked_hours = calculate_task_worked_hours(submissionData.filter(quotation=quotationId))
        
        task_data = {
            "id": taskID,
            "name": taskName,
            "assignedId" : asignedId,
            "assignBy":assignBy,
            "workedHours": append_default_actual_worked_hours(task_worked_hours.get(item["task"], {}), startDate)
        }
        
        milestone_data = {
            "milestoneId": milestoneId,
            "milestoneName": milestoneName,
            "workedHours": append_default_actual_worked_hours(milestone_worked_hours.get(milestoneId, {}), startDate),
            "tasks": [task_data]
        }
        if not milestoneId and not taskID:
            noTaskQuotation[re.sub(r'[^a-zA-Z0-9]', '', quotationId)] = asignedId

        if quotationId in grouped_data:
            existing_milestone = next((m for m in grouped_data[quotationId]["milestones"] if m["milestoneId"] == milestoneId), None)
            if existing_milestone:
                existing_milestone["tasks"].append(task_data)
            else:
                grouped_data[quotationId]["milestones"].append(milestone_data)
        else:
            grouped_data[quotationId] = {
                "quotationId": quotationId,
                'customerName' :customerName, 
                'customprojectName' :customprojectName, 
                'systemName' : systemName, 
                'customerCode' : customerCode,
                "projectId": projectId,
                "projectName": projectName,
                "workedHours": append_default_actual_worked_hours(projectHoursDict.get(quotationId, {}), startDate),
                "milestones": [milestone_data]
            }
    return grouped_data,noTaskQuotation

def calculate_milestone_worked_hour(data):
    milestoneHours = defaultdict(lambda: defaultdict(int))
    for item in data:
        milestoneId = item['milestone']
        date_str = item['date'].strftime('%d-%m-%Y')
        milestoneHours[milestoneId][date_str] += item['total_hrs']
    milestoneHoursDict = {
            milestoneId: {date: hours for date, hours in worked_hours.items()}
        for milestoneId, worked_hours in milestoneHours.items()
    }
    return milestoneHoursDict

def calculate_task_worked_hours(data):
    taskHours = defaultdict(lambda: defaultdict(int))
    for task in data:
        taskId = task['task']
        date_str = task['date'].strftime('%d-%m-%Y')
        taskHours[taskId][date_str] += task['total_hrs']
    taskHoursDict = {
            taskId: {date: hours for date, hours in worked_hours.items()}
        for taskId, worked_hours in taskHours.items()
    }
    return taskHoursDict

def append_default_actual_worked_hours(actualWorkHrs: Dict[str, int], startDate: str) -> Dict[str, int]:
    week_days = pd.date_range(startDate, periods=7).strftime('%d-%m-%Y')
    default_worked_hours = {date: actualWorkHrs.get(date, 0) for date in week_days}
    
    return default_worked_hours

# new update hours ..........................
def update_timesheet(request):
    try:
        # Parse date, task ID, hours, and project ID from request
        date = datetime.strptime(request.POST.get('date'), "%d-%m-%Y").date()
        hours = request.POST.get('hours')
        assignId = request.POST.get('assignId') or assign_nonproject(request)
        userid = request.user.id

        assignedBy = AssignedTask.objects.get(pk = assignId)

        # Fetch existing submission data for the given task and date
        submission_data = Submission.objects.filter(assignId=assignId,date=date).first()
 
        # Calculate total hours for the day excluding current task
        hrs_per_day = Submission.objects.filter(date=date,assignId__assignTo =userid).aggregate(sum=Sum('hours'))
       
        # Convert hours to duration in seconds
        if hours.__contains__('.'):
            duration = timedelta(hours=int(hours.split('.')[0]) if hours.split('.')[0] != '' else 0,
                                minutes=int(hours.split('.')[1]) if hours.split('.')[1] != '' else 0).total_seconds()
        else:
            duration = timedelta(hours=int(hours.split('.')[0]) if hours.split('.')[0] != '' else 0).total_seconds()
    
        # Calculate total duration including existing hours
        duration_ = duration + (hrs_per_day['sum'] or 0)
        if submission_data:
            duration_ -= submission_data.hours
        # Check if total duration exceeds limit (14 hours)
        if duration_ <= 50400:
            if not submission_data:
                # Create new timesheet entry if none exists
                submission_model = Submission(
                    assignId_id=assignId,
                    date=date,
                    hours=duration, 
                    approvedBy = assignedBy.assignBy
                )
                logger.info(f"Creating new timesheet entry for {userid} on {date} for task  with {duration} hours")
            else:
                # Update existing timesheet entry
                submission_model = submission_data
                if duration != 0.0:
                    submission_model.hours = duration
                else:
                    submission_model.delete()

            if duration != 0.0:
                logger.info(f"Updating timesheet entry for {userid} on {date} for task  with {duration} hours")
                submission_model.save()
            return {"status": "valid"}
        else:
            logger.info(f"Deleting timesheet entry for {userid} on {date} for task  as hours are zero")
            return {"status": "invalid"}
    except DatabaseError as db_error:
        # Log database errors
        logger.error("Database error  for user %s: %s", request.user.id, db_error)
        return JsonResponse({"error": f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        # Log the error details for debugging purposes
        logger.error(f"Error handling timesheet update: {str(e)}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred. Please try again later."}

def assign_nonproject(request):
    user = request.user
    milestone = request.POST.get('milestone_id')
    task = request.POST.get('task_id')
    milestone_name = request.POST.get('milestone_name')
    task_name = request.POST.get('task_name')
    existing_task = AssignedTask.objects.filter(
        assignTo=user, 
        milestone=milestone, 
        task=task,
        milestoneName=milestone_name, 
        taskName=task_name
    ).select_related('assignTo').first()
    
    if existing_task:
        if existing_task.assignBy_id != request.user.reporting_to_id:
            existing_task.assignBy_id = request.user.reporting_to_id
            existing_task.save()
        assign_id = existing_task.id

    else:
        new_task = AssignedTask.objects.create(
            assignTo=user,
            quotation="Non project",
            assignBy=user.reporting_to,
            milestone=milestone, 
            task=task,
            milestoneName=milestone_name, 
            taskName=task_name
        )
        assign_id = new_task.id
    return assign_id

# 
def handle_duplicate_assign_tasks(user, start_date):
    try:
        AssignedTask.objects.filter(
            Q(end_date__range=[start_date, start_date + timedelta(days=6)]) &
            Q(assignTo=user)
        ).update(end_date = start_date + timedelta(days=13))
    except DatabaseError as db_error:
        # Log database errors
        logger.error("Database error while fetching quotations for user %s: %s", user.first_name, db_error)
        return JsonResponse({"error": f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error updating milestones: {str(e)}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred. Please try again later."}

def handle_remove_assign_task(user, post_data, start_date):
    try:
        assignedIdList = json.loads(post_data.get('assignedIdList'))
        timesheetData = AssignedTask.objects.values('id','quotation','milestone','milestoneName','task','taskName').filter(id__in=assignedIdList)
        if get_submission_Status(timesheetData, start_date, user):
            assigned_task = AssignedTask.objects.filter(pk__in=assignedIdList)
            for assigned_milestone in assigned_task:
                if assigned_milestone.start_date < start_date.date():
                    assigned_milestone.end_date = start_date - timedelta(days=1)
                    assigned_milestone.save()
                else:
                    assigned_milestone.delete()
            return True
        return False
    except DatabaseError as db_error:
        # Log database errors
        logger.error("Database error while fetching quotations for user %s: %s", user.id, db_error)
        return JsonResponse({"error": f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error updating milestones: {str(e)}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred. Please try again later."}

def handle_submission(user, start_date, current_date, Comments):
    timesheet_entries = Submission.objects.filter(
        Q(assignId__assignTo=user),
        Q(date__range=[start_date, start_date + timedelta(days=6)]),
        Q(Q(status="Rejected")|Q(status= None))
    )
    for entry in timesheet_entries:
        entryObject = Submission.objects.get(pk=entry.id)
        entryObject.status = "Submitted"
        entryObject.approvedBy = entryObject.assignId.assignBy
        entryObject.save()

    timesheet_status_entry, created = TimesheetStatus.objects.get_or_create(
        uid=user,
        weeknumber = start_date.strftime("%V"),
        weekyear = start_date.year,
        defaults={
            'timesheet_status': 'Submitted',
            'submission_status': (start_date + timedelta(days=6)).date() >= current_date.date(),
            'action_status': False,
            'comments':Comments
        }
    )
    timesheetOverAllStatus = timesheet_status_entry.timesheet_status
    if not created and (timesheetOverAllStatus == "Rejected" or timesheetOverAllStatus == "Unlocked"):
        timesheet_status_entry.timesheet_status = "Submitted"
        timesheet_status_entry.submission_status = (start_date + timedelta(days=6)).date() >= current_date.date()
        timesheet_status_entry.comments = Comments
        timesheet_status_entry.save()
    send_submission_email(user, start_date)

def get_submission_Status(data,startDate,user):
    try:
        for item in data:
            try:
                if Submission.objects.filter(Q(date__gte = startDate)&
                                                    Q(assignId__assignTo_id = user.id)&
                                                    Q(assignId__quotation = item['quotation'])&
                                                    Q(assignId__milestone = item['milestone'])&
                                                    Q(assignId__milestoneName = item['milestoneName'])&
                                                    Q(assignId__task = item['task'])&
                                                    Q(assignId__taskName = item['taskName'])):
                    return False
            except DatabaseError as db_error:
                # Handle database errors specifically
                logger.error("Database error while checking for submissions: %s", db_error, exc_info=True)
                return False  # Return False to indicate failure
        return True
    except Exception as e:
        # Catch all other unexpected errors
        logger.error("Unexpected error in get_submission_Status: %s", str(e), exc_info=True)
        return False  # Return False to indicate an error state

def send_submission_email(user, start_date):
    end_date = start_date + timedelta(days=6)

    reporter = getattr(user, 'reporting_to', None)
    reporter_name = getattr(reporter, 'first_name', 'Reporting Manager')
    reporter_email = getattr(reporter, 'email', None)

    if not reporter_email:
        print("No reporter email found. Email not sent.")
        return

    # Email details
    subject = f"Timesheet Submission Notification: {user.first_name} ({start_date.strftime('%G')} - Week {start_date.strftime('%V')})"
    text_content = f"{user.first_name} has submitted their timesheet for the week starting {start_date.strftime('%d %b %Y')}."
    
    # HTML content using your existing body generator
    html_content = submitedEmailBody(
        reporter_name,
        user.first_name,
        start_date.strftime("%G"),  # ISO year
        start_date.strftime("%V"),  # ISO week number
        start_date.date(),
        end_date.date()
    )

    # Send email
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        "icproprojects@gmail.com",
        [reporter_email],
        cc=[user.email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def handle_rejection_reasons(user, start_date):
    rejected_reasons = Submission.objects.filter(
        assignId__assignTo_id=user.id,
        timesheet_status="Rejected",
        date__range=[start_date, start_date + timedelta(days=6)]
    ).values("taskName", "rejection_reason").distinct()
    return JsonResponse({"rejectedReasons": list(rejected_reasons)})

# for undefined quotation
def fetchServiceMilestonesTasks(request):
    serviceMilestoneGroupWise = list(phaseCategory.objects.values_list('category').filter(phases__name='Site Services'))
    serviceMilestonesTasks = CostMaster.objects.using('erp').values(
        'id', 'name', 'cost_category__id', 'cost_category__name'
    ).filter(cost_category__in = serviceMilestoneGroupWise)

    serviceMilestoneList = []

    # Loop through tasks and group them by milestone
    for item in serviceMilestonesTasks:
        # Check if the milestone already exists in the list
        existing_milestone = next(
            (milestone for milestone in serviceMilestoneList if milestone['milestone'] == item['cost_category__id']),
            None
        )
        if not existing_milestone:
            # Create a new milestone entry if it doesn't exist
            serviceMilestoneList.append({
                'milestone': item['cost_category__id'],
                'milestoneName': item['cost_category__name'],
                'tasks': [{'task': item['id'], 'taskName': item['name']}]
            })
        else:
            # Append the task to the existing milestone's tasks
            existing_milestone['tasks'].append({'task': item['id'], 'taskName': item['name']})
    return JsonResponse({"serviceMilestoneList":serviceMilestoneList})

@csrf_exempt
def assignUndefinedQuotation(request):
    if request.method == 'POST':
        assignments=[]
        # undefinedQuotation = generate_quotation_number(),
        start_date = datetime.strptime(request.POST.get('fromDate'),'%d-%b-%Y')
        checkedItems = json.loads(request.POST.get('checkedItems'))
        for item in checkedItems:
            assignments.append(AssignedTask(
                quotation=generate_quotation_number(),
                customprojectName = request.POST.get('undefinedProjectName'),
                projectName = request.POST.get('undefinedProjectName'),
                customerName = request.POST.get('undefinedcustomerName'),
                milestone=item['milestone'],
                milestoneName=item['milestoneName'],
                task=item['task'],
                taskName=item['taskName'],
                assignBy=request.user.reporting_to,
                assignTo =request.user,
                start_date=start_date,
                end_date=start_date + timedelta(days=6)
            ))
        # Bulk create new assignments
        if assignments:
            AssignedTask.objects.bulk_create(assignments)
        # undefined project with no milestone and task
        else:
            AssignedTask(
                quotation=generate_quotation_number(),
                customerName = request.POST.get('undefinedcustomerName'),
                customprojectName = request.POST.get('undefinedProjectName'),
                projectName = request.POST.get('undefinedProjectName'),
                assignBy=request.user.reporting_to,
                assignTo =request.user,
                start_date=start_date,
                end_date=start_date + timedelta(days=6)
            ).save()
    return JsonResponse({"status":"ok"})
        
def generate_quotation_number():
    # Fetch the highest quotation number from the database
    latest_quotation = AssignedTask.objects.filter(
        quotation__startswith='ICP/UN/'  # Only consider relevant quotations
    ).aggregate(max_number=Max('quotation'))

    # Extract the numeric part of the latest quotation number
    latest_number = latest_quotation['max_number']
    if latest_number:
        # Extract the numeric part, e.g., 'ICP/UN/0001' -> 1
        current_number = int(latest_number.split('/')[-1])
    else:
        current_number = 0  # Start from zero if no quotations exist
    
    # Increment the number and format it with leading zeros
    new_number = current_number + 1
    formatted_number = f"ICP/UN/{new_number:04d}"  # Format as 'ICP/UN/XXXX'
    
    return formatted_number

#.................................Update Assigner....................................
@csrf_exempt
def update_assigner(request):
    """
    Updates the assigned tasks for a user based on the provided task IDs and new assigned_by user.
    """
    try:
        ids = request.POST.get('assignId')
        assigned_by = request.POST.get('assign_by')

        # Validate input fields
        if not ids or not assigned_by:
            logger.warning("Missing required fields: ids or assigned_by.")
            return JsonResponse({'error': 'Required fields missing (ids or assigned_by).'}, status=400)

        # Parse IDs
        try:
            ids_list = json.loads(ids)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for ids: {str(e)}")
            return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)

        # Validate IDs list
        if not isinstance(ids_list, list) or not ids_list:
            logger.warning("Invalid or empty IDs list provided.")
            return JsonResponse({'error': 'Invalid or empty IDs list.'}, status=400)

        # Update assigned_by field for the specified tasks
        AssignedTask.objects.filter(id__in=ids_list).update(assignBy=assigned_by)

        return JsonResponse({'success': True, 'message': 'Assigned tasks updated successfully.'})

    except Exception as e:
        logger.exception("An unexpected error occurred during task update.")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)

@csrf_exempt
def unlock_timesheet(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    try:
        from_date_str = request.POST.get('fromDate')
        unlock_reason = request.POST.get("reason")

        if not from_date_str or not unlock_reason:
            return JsonResponse({'success': False, 'message': 'Missing required data.'}, status=400)

        week_start_date = datetime.strptime(from_date_str, '%d-%b-%Y')
        day_difference = (datetime.today().date() - week_start_date.date()).days

        if not (0 < day_difference <= 130):
            return JsonResponse({'success': False, 'message': 'Timesheet can only be unlocked for the current or previous week.'}, status=400)

        # Check if the timesheet is already unlocked
        existing_timesheet = TimesheetStatus.objects.filter(
                                                            uid=request.user,
                                                            weeknumber=week_start_date.strftime("%V"),
                                                            weekyear=week_start_date.year
                                                        ).first()  # Use first() to get one object
        if existing_timesheet:
            if existing_timesheet.unlock_status in ["Accepted", "Requested"]:
                return JsonResponse({'success': False, 'message': 'Timesheet unlock already requested or accepted for the given week.'}, status=400)
            else:
                existing_timesheet.unlock_status = "Requested"
                existing_timesheet.unlock_reason = unlock_reason
                existing_timesheet.save()
        else:
            TimesheetStatus.objects.create(
                timesheet_status="locked",
                weeknumber=week_start_date.strftime("%V"),
                submission_status= False,#(week_start_date + timedelta(days=6)).date() >= datetime.today().date(),
                action_status= False, #getSubmissionStatus(week_start_date),
                unlock_status="Requested",
                weekyear=week_start_date.year,
                uid=request.user,
                unlock_reason=unlock_reason
            )
        # send_unlock_email(request.user, week_start_date)
        return JsonResponse({'success': True, 'message': 'Timesheet unlock request send successfully.'})

    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format.'}, status=400)

    except Exception as e:
        logger.exception("An unexpected error occurred while unlocking timesheet.")
        return JsonResponse({'success': False, 'message': f'An internal error occurred: {str(e)}'}, status=500)

def getSubmissionStatus(week_start_date):
    currentdate = datetime.today()
    approvalLastDate = week_start_date + timedelta(days=13)
    if approvalLastDate.date() >= currentdate.date():
        return True
    return False

@csrf_exempt
def accept_unlock_request(request):
    try:
        id = request.POST.get('id')
        if not id:
            return JsonResponse({'success': False, 'message': 'Missing timesheet ID.'}, status=400)

        updated = TimesheetStatus.objects.filter(pk=id).update(timesheet_status="Unlocked",unlock_status = "Accepted")

        if updated == 0:
            return JsonResponse({'success': False, 'message': 'No timesheet found with the given ID.'}, status=404)
        unlockApprovedEmailSend(id)
        return JsonResponse({'success': True, 'message': 'Timesheet unlocked successfully.'})
    except Exception as e:
        logger.error(f"Error unlocking timesheet with ID {id}: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An error occurred while unlocking timesheet.'}, status=500)

@csrf_exempt
def reject_unlock_request(request):
    try:
        id = request.POST.get('id')
        if not id:
            return JsonResponse({'success': False, 'message': 'Missing timesheet ID.'}, status=400)

        updated = TimesheetStatus.objects.filter(pk=id).update(unlock_status="Rejected")

        if updated == 0:
            return JsonResponse({'success': False, 'message': 'No timesheet found with the given ID.'}, status=404)

        return JsonResponse({'success': True, 'message': 'Timesheet unlocked successfully.'})

    except Exception as e:
        logger.error(f"Error unlocking timesheet with ID {id}: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An error occurred while unlocking timesheet.'}, status=500)

def unlockApprovedEmailSend(timesheetStatusId):
    unlockData = TimesheetStatus.objects.filter(pk=timesheetStatusId).values('uid__reporting_to__email','uid__first_name','uid__email','weeknumber')

    # Email details
    subject = f"Timesheet Unlock request approved"
    text_content = f"{unlockData[0]['uid__first_name']}'s Timesheet is Unlocked."

    # HTML content using your existing body generator
    html_content = UnlockApprovedEmailBody(
        unlockData[0]['uid__first_name'],unlockData[0]['weeknumber']
    )

    # Send email
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        "icproprojects@gmail.com",
        [unlockData[0]['uid__email']],
        cc=[unlockData[0]['uid__reporting_to__email']]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

#-------------------------------- approval ----------------------------------------
# load submission page
@csrf_protect
@login_required(login_url='home')
@unathenticated
def allTimesheetLog(request):
    if request.user.role != "Employee":
        return render(request,'approval.html',{"module":"timesheet"})  
    return HttpResponse("Sorry!! You are not Authorized")

# get approval tabledata
@csrf_exempt
@login_required(login_url='home')
def get_summary_template(request):
    # Get the current date and time
    current_date = datetime.today()
    # Find the current weekday (0 = Monday, 6 = Sunday)

    week_start_date = current_date - timedelta(days=current_date.weekday())

    # Handle POST requests
    if request.method == 'POST':
        # Extract the employee ID and start date from the request
        employee_id = request.POST.get('empl_id')
        present_week_start_date = datetime.strptime(request.POST.get('fromdate_'), '%d-%b-%Y')
        
        # Extract the mode of operation from the request
        mode = request.POST.get('mode')
        
        # Adjust the week start date based on the mode
        if mode == 'postdate':
            week_start_date = present_week_start_date + timedelta(days=7)
        elif mode == 'predate':
            week_start_date = present_week_start_date - timedelta(days=7)
        elif mode == 'detailed_view':
            # Return detailed view data for the given week and employee
            return detailed_ViewTable_Data(present_week_start_date, employee_id)
        elif mode == 'update':
            approvalLastDate = present_week_start_date + timedelta(days=13)
            # Handle timesheet submission and status actions
            handle_timesheet_submission_action(request, present_week_start_date, employee_id,current_date, approvalLastDate)

            handle_timesheet_status_action(request, present_week_start_date, employee_id, current_date, approvalLastDate)
            # Return the detailed view after actions are performed
            return detailed_ViewTable_Data(present_week_start_date, employee_id)
        else:
            week_start_date = present_week_start_date
            
    # Calculate the end date of the week
    week_end_date = week_start_date + timedelta(days=6)
    # Prepare the context data for the approval view
    context,unlockResqued = prepare_context_approval_data(request.user, week_start_date, week_end_date, current_date)
    dayDifference = (current_date.date() - week_start_date.date()).days
    unlockStatus = False
    if 0 < dayDifference and dayDifference <= 13 : 
        unlockStatus= True
    # Return the data as a JSON response
    return JsonResponse({
        "currentdate": datetime.strftime(current_date, '%d-%b-%Y'),
        'tabledata': list(context),  # Convert context data to a list for JSON serialization
        'unlockResqued':list(unlockResqued),
        'weeknum':  week_start_date.strftime("%V"),  # Return the week number
        "unlockStatus" : unlockStatus,
        "week_start_date": datetime.strftime(week_start_date, '%d-%b-%Y'),
        "week_end_date": datetime.strftime(week_end_date, '%d-%b-%Y')
    })

def handle_timesheet_submission_action(request,present_week_start_date,employee_id,current_date,approvalLastDate):
    value = request.POST.get('value')
    field = request.POST.get('field')
    assignId = request.POST.get('assignId')
    rejection_reason = request.POST.get('rejectionReason', "")
    present_week_end_date = present_week_start_date + timedelta(days=6)

    # Fetch the relevant timesheet entries
    timesheet_ids = Submission.objects.filter(
        Q(assignId=assignId) &
        Q(date__range=[present_week_start_date, present_week_end_date])
    ).values_list('id', flat=True)
    # Prepare update data based on the field being updated
    update_data = {}
    update_data['approved_status'] = True

    if approvalLastDate.date() <= current_date.date():
        update_data['approved_status'] = False

    if field != 'status':
        update_data['rate'] = value
    else:
        update_data['status'] = value
        if rejection_reason:
            update_data['rate'] = 0  # Reset the rate if a rejection reason is provided
            update_data['rejection_reason'] = rejection_reason
    # Perform bulk update if there are any timesheet entries
    if timesheet_ids:
        with transaction.atomic():
            submissions = Submission.objects.select_for_update().filter(id__in=timesheet_ids)
            for submission in submissions:
                for key, value in update_data.items():
                    setattr(submission, key, value)
                submission.save()

    # email when user rejected the timesheet
    if rejection_reason != "":
        handle_send_rejection_email(employee_id,present_week_start_date,timesheet_ids,rejection_reason)

def handle_timesheet_status_action(request,present_week_start_date,employee_id,current_date,approvalLastDate):
    timesheetStatusList = Submission.objects.values_list('status',flat=True)\
                            .filter(Q(date__range=[present_week_start_date,present_week_start_date+timedelta(days=6)]),
                                    Q(assignId__assignTo=employee_id))\
                            .distinct()
    
    timesheetStatusObject = TimesheetStatus.objects.get(uid_id=employee_id,
                                                        weeknumber=present_week_start_date.strftime("%V"),
                                                        weekyear=present_week_start_date.year)
    
    if approvalLastDate.date() >= current_date.date():
        if timesheetStatusObject.action_status==False:
            timesheetStatusObject.action_status = True
    status = ""
    if "Rejected" in timesheetStatusList:
        status="Rejected"
    else:
        status = "Submitted" if "Submitted" in timesheetStatusList else "Accepted"
    if timesheetStatusObject.timesheet_status != status:
        timesheetStatusObject.timesheet_status = status
    timesheetStatusObject.save()
        
def handle_send_rejection_email(employee_id,present_week_start_date,timesheetId,reason):
  # Fetch user details
    user_details = users.objects.values(
        'first_name',
        'email',
        reportingManagerEmail=F('reporting_to__email'),
        reportingManagerName=F('reporting_to__first_name')
    ).filter(id=employee_id)

    if not user_details:
        print("Invalid employee ID.")
        return

    user = user_details[0]

    # Get task details
    task_details = Submission.objects.values(
        'assignId__quotation', 'assignId__projectName', 'assignId__taskName'
    ).filter(id=int(timesheetId[0]))

    if not task_details:
        print("Invalid timesheet ID.")
        return

    task = task_details[0]

    project_label = f"{task['assignId__quotation']} - {task['assignId__projectName']}" if task['assignId__projectName'] else task['assignId__quotation']

    # Prepare email
    subject = 'Timesheet Rejected for Week {}-{}'.format(
        present_week_start_date.strftime("%G"), present_week_start_date.strftime("%V")
    )

    text_content = f"""
    Your timesheet has been rejected by your reporting manager.
    Week: {present_week_start_date.strftime("%G")} - {present_week_start_date.strftime("%V")}
    Reason: {reason}
    """

    html_content = rejectedEmailBody(
        user["first_name"],
        user["reportingManagerName"],
        present_week_start_date.strftime("%G"),
        present_week_start_date.strftime("%V"),
        present_week_start_date.date(),
        (present_week_start_date + timedelta(days=6)).date(),
        project_label,
        task['assignId__taskName'],
        reason
    )

    # Send email
    msg = EmailMultiAlternatives(
        subject,
        text_content.strip(),
        "icproprojects@gmail.com",
        [user["email"]],
        cc=[user["reportingManagerEmail"]]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def prepare_context_approval_data(user, week_start_date, week_end_date, current_date):
    # Base query for fetching active users who joined before or on the week start date, excluding certain roles
    tabledata = users.objects.exclude(role__in=['Consultant', 'Admin','HR','CEO']) \
                             .filter(is_active=True, date_joined__lte=week_start_date) \
                             .values('first_name', 'id', reporter_name=F('reporting_to__first_name'))

    assignedBy_User = AssignedTask.objects.values_list('assignTo',flat=True).filter(assignBy = user, end_date__gte=week_start_date, start_date__lte=week_end_date).distinct()
    
    # If the user is Admin or Consultant, further filter based on reporting_to
    if user.role not in ['Admin','Consultant','CEO','HR']:
        tabledata = tabledata.filter(Q(reporting_to=user) | Q(id__in = assignedBy_User))
    
    # Convert to a list to prepare for updates
    tabledata = list(tabledata)

    # Get all relevant timesheet statuses in a single query
    timesheet_data = TimesheetStatus.objects.filter(
        Q(weeknumber=week_start_date.strftime("%V")) & Q(weekyear=week_start_date.year) & Q(uid_id__in=[i['id'] for i in tabledata])
    ).values('id','uid_id','uid__first_name', 'timesheet_status','unlock_status','unlock_reason').annotate(
        submission_status=Case(
            When(submission_status=True, then=Value('OnTime')),
            default=Value('Delayed'),
            output_field=CharField(),
        ),
        action_status=Case(
            When(action_status=True, then=Value('OnTime')),
            default=Value('Delayed'),
            output_field=CharField(),
        )
    )
    unlockResqued = timesheet_data
    if user.role != 'Admin':
        unlockResqued = timesheet_data.filter(uid__reporting_to =user)

    # Create a dictionary to map user id to timesheet data
    timesheet_dict = {data['uid_id']: data for data in timesheet_data}

    # Get total hours worked in the week for all users in a single query
    weekhours_data = Submission.objects.filter(
        Q(assignId__assignTo__in=[i['id'] for i in tabledata]) & Q(date__range=[week_start_date, week_end_date])
    ).values(uid_id =F('assignId__assignTo')).annotate(total_hours=Sum('hours'))

    # Create a dictionary to map user id to week hours
    weekhours_dict = {data['uid_id']: data['total_hours'] for data in weekhours_data}
    
    approvalLastDate = week_end_date + timedelta(days=7)

    # Iterate over tabledata to update with the relevant information
    for i in tabledata:
        user_id = i['id']
        
        # Fetch timesheet status data for this user
        timesheet_info = timesheet_dict.get(user_id, {})

        # Determine timesheet status
        timesheetStatus = timesheet_info.get('timesheet_status')
        if not timesheetStatus:
            timesheetStatus = "Due by " + datetime.strftime(week_end_date, '%d-%b-%Y') \
                              if week_end_date.date() >= current_date.date() else "NotSubmitted"
        
        # Fetch total hours worked for this user
        week_hours = weekhours_dict.get(user_id, 0)
        formatted_hours = secondToHours(week_hours)[:-3] if week_hours else '00.00'
        
        defaultStatus ="Due by "+datetime.strftime(week_end_date,'%d-%b-%Y') if week_end_date.date() >= current_date.date() else "Delayed"
        approvalDefaultStatus ="Due by "+datetime.strftime(approvalLastDate,'%d-%b-%Y') if approvalLastDate.date() >= current_date.date() else "Delayed"

        # Update the dictionary with the gathered information
        i.update({
            'timesheet_status': timesheetStatus,
            'Week_hours': formatted_hours,
            'unlock_status':timesheet_info.get('unlock_status'),
            'unlock_reason':timesheet_info.get('unlock_reason'),
            'submissionStatus': timesheet_info.get('submission_status', defaultStatus),
            'actionStatus': approvalDefaultStatus if timesheet_info.get('action_status', approvalDefaultStatus)=="Delayed" else timesheet_info.get('action_status', approvalDefaultStatus)
        })
    # Return the updated tabledata
    return tabledata,unlockResqued

# detailed view data 
def detailed_ViewTable_Data(present_week_start_date,employee_id):
    week_start_date = present_week_start_date
    weekDays =[d.date() for d in pd.date_range(week_start_date, periods=7)]
    week_end_date = present_week_start_date +  timedelta(days=6)

    submittedData = Submission.objects.annotate(quotation=F('assignId__quotation'),
                                                project=F('assignId__project'),
                                                projectName=F('assignId__projectName'),
                                                milestone=F('assignId__milestone'),
                                                milestoneName=F('assignId__milestoneName'),
                                                task=F('assignId__task'),
                                                taskName=F('assignId__taskName'),
                                                timesheet_status=F('status'),
                                                total_hrs=Sum('hours')).values('id',
                                                                            'rate',
                                                                            'date',
                                                                            'rejection_reason',
                                                                            'quotation',
                                                                            'project',
                                                                            'projectName',
                                                                            'milestone',
                                                                            'milestoneName',
                                                                            'task',
                                                                            'taskName',
                                                                            'total_hrs',
                                                                            'timesheet_status',
                                                                            'assignId')\
                                                            .filter(date__range=[week_start_date, week_end_date], assignId__assignTo= employee_id)\
                                                            .order_by('quotation','milestoneName','taskName')
    
    tasksdata = Submission.objects.annotate(quotation=F('assignId__quotation'),
                                            customerName=F('assignId__customerName'),
                                            customprojectName=F('assignId__customprojectName'),
                                            assignBy=F('assignId__assignBy'),
                                            assignByName=F('assignId__assignBy__first_name'),
                                            project=F('assignId__project'),
                                            projectName=F('assignId__projectName'),
                                            milestone=F('assignId__milestone'),
                                            milestoneName=F('assignId__milestoneName'),
                                            task=F('assignId__task'),
                                            taskName=F('assignId__taskName'),
                                            ).values('assignId',
                                                    'quotation',
                                                    'customerName',
                                                    'customprojectName',
                                                    'assignBy',
                                                    'assignByName',
                                                    'project',
                                                    'projectName',
                                                    'milestone',
                                                    'milestoneName')\
                                            .filter(Q(assignId__assignTo  = employee_id)& Q(date__range=[week_start_date,week_end_date]))\
                                            .distinct().order_by('quotation','milestoneName','taskName')
    
    taskList = handle_rate_date(submittedData)
    projectHoursDict,weekDaysHrs = calculate_project_worked_hours(submittedData)
    timesheetData = handle_Timesheet_data_Approval(tasksdata,projectHoursDict,week_start_date,submittedData)

    tableHeader = [datetime.strftime(d,'%a-%d') for d in pd.date_range(present_week_start_date, periods=7)]
    nonProject = []
    if 'Non project' in timesheetData:
        nonProject.append(timesheetData.pop('Non project'))

    comments = TimesheetStatus.objects.filter(Q(uid_id  = employee_id) & Q(weeknumber=week_start_date.strftime("%V")) & Q(weekyear=week_start_date.year)).values('comments')
    return JsonResponse({'emp_deailed_data':list(timesheetData.values()),
                         "nonProjectdata":nonProject,
                         'week_days':list(tableHeader),
                         'cell_date':list(weekDays),"taskList":taskList,
                         'estimatedHours':calculate_estimated_hours(week_start_date),
                         'comments':list(comments)})    

# collecting rating data,status,reason
def handle_rate_date(data):
    data =data.values('id','rate','rejection_reason','quotation','task','timesheet_status').distinct()
    # grouped_data = defaultdict(dict)
    grouped_data_ = {}
    for item in data:
        quotation = item["quotation"]
        task =item["task"]
        rate =item["rate"]
        timesheet_status = item["timesheet_status"]
        rejectionReason =item["rejection_reason"]
        # # Prepare tasks data
        task_data ={
            "task":task,
            "rate":rate,
            "timesheet_status":timesheet_status,
            "rejectionReason":rejectionReason
        }
        # # Add to grouped data
        if quotation in grouped_data_:
            grouped_data_[quotation].append(task_data)
        else:
            grouped_data_[quotation] = [task_data]
    # Process each entry in the input data
    return grouped_data_

def handle_Timesheet_data_Approval(data,projectHoursDict,startDate,submissionData):
    # Dictionary to hold grouped data
    grouped_data = {}
    # Iterate over original data
    for item in data:
        project = item["project"]
        projectName = item["projectName"]
        quotation = item["quotation"]
        milestone = item["milestone"]
        milestoneName = item["milestoneName"]
        customerName = item["customerName"]
        customprojectName = item["customprojectName"]
        assignBy = item["assignBy"]  
        assignByName = item["assignByName"]
        assignId =item['assignId']
        
        # Check if projectName already exists in grouped_data
        if quotation in grouped_data:
            # Append milestone to existing entry
            grouped_data[quotation]["milestones"].append({
                "milestone": milestone,
                "milestoneName": milestoneName,
                "workedHours": append_default_actual_worked_hours(calculate_milestone_worked_hour(submissionData.filter(quotation=quotation))[item['milestone']],startDate) if item['milestone'] in calculate_milestone_worked_hour(submissionData.filter(quotation=quotation)) else append_default_actual_worked_hours({},startDate),
                "tasks":[
                    {
                        "id": item['task'],
                        "assignId":assignId,
                        "name": item["taskName"],
                        "customerName":customerName,
                        "customprojectName":customprojectName,
                        "assignBy":assignBy,
                        "assignByName":assignByName,
                        "workedHours":append_default_actual_worked_hours(calculate_task_worked_hours(submissionData.filter(quotation=quotation))[item['task']],startDate) if item['task'] in calculate_task_worked_hours(submissionData.filter(quotation=quotation)) else append_default_actual_worked_hours({},startDate)
                    } for item in submissionData.filter( Q(assignId = assignId)).values('task','taskName').distinct()
                ] 
            })
        else:
            # Create new entry in grouped_data
            grouped_data[quotation] = {
                "project": project,
                "projectName": projectName,
                "quotation": quotation,
                "workedHours":append_default_actual_worked_hours(projectHoursDict[quotation],startDate) if quotation in projectHoursDict else append_default_actual_worked_hours({},startDate),
                "milestones": [{
                    "milestone": milestone,
                    "milestoneName": milestoneName,
                    "workedHours": append_default_actual_worked_hours(calculate_milestone_worked_hour(submissionData.filter(quotation=quotation))[item['milestone']],startDate) if item['milestone'] in calculate_milestone_worked_hour(submissionData.filter(quotation=quotation)) else append_default_actual_worked_hours({},startDate),
                    "tasks":[
                    {
                        "id": item['task'],
                        "name": item["taskName"],
                         "assignId":assignId,
                        "customerName":customerName,
                        "customprojectName":customprojectName,
                        "assignBy":assignBy,
                        "assignByName":assignByName,
                        "workedHours":append_default_actual_worked_hours(calculate_task_worked_hours(submissionData.filter(quotation=quotation))[item['task']],startDate) if item['task'] in calculate_task_worked_hours(submissionData.filter(quotation=quotation)) else append_default_actual_worked_hours({},startDate)
                    } for item in submissionData.filter( Q(assignId = assignId)).values('task','taskName').distinct()
                ]
                }]
            }
    
    return grouped_data

def send_unlock_email(userData, start_date):
    end_date = start_date + timedelta(days=6)

    # Extract user and reporter details
    reporter_email = userData.reporting_to.email
    user_name = userData.reporting_to.first_name
    user_email = userData.email
    name =userData.first_name
    # Subject & basic content
    subject = f"Timesheet Unlock Request for Week {start_date.strftime('%V')} - {start_date.strftime('%G')}"
    text_content = (
        f"Dear {user_name},<br><br>"
        f"<strong style='color: rgb(65, 160, 41);'>Timesheet Locked.</strong><br><br>"
        f"This is to inform you that {name}'s timesheet has been locked.<br>"
        f"Year: {start_date.strftime('%G')}, Week: {start_date.strftime('%V')}, "
        f"Period: {start_date.date()} to {end_date.date()}."
        f"<br><br>"
        f"This request has been submitted to unlock the timesheet for this period, accompanied by a valid explanation.<br>"
        f"knidly approve the request at your earliest convenience.<br>"
        f"<br><br>" 
        f"click here to unlock the timesheet<br>"
        f"<a href='https://tsm.icpro.in'>https://tsm.icpro.in</a>"
    )
    # HTML content using your custom template function
    html_content = lockedEmailBody(text_content)

    # Construct and send the email
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        "icproprojects@gmail.com",      # From
        [reporter_email],                   # To
        cc=[user_email]            # CC to manager
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

#-------------------------- common function --------------------------------
def secondToHours(seconds):
    if seconds and seconds!=0:
        h, m, s = map(lambda x: int(x), [seconds/3600, seconds%3600/60, seconds%60])
        return f'{h}.{m:02d}.{s:02d}'
    return f'{00}.{00}'

# weekly submision reminder
def emailsend(request):
    currentDate = datetime.today()
    weekday = currentDate.weekday()
    week_end_date = currentDate - timedelta(days=1)
    if weekday == 4:
        nextSaturday = currentDate + timedelta(days=1)
        day = nextSaturday.day
        if (8 <= day and day < 15) or (22 <= day and day < 29):
            week_end_date = currentDate + timedelta(days=2)
        else:
            return ''
    if weekday == 5:
        day = currentDate.day
        if (8 <= day and day < 15) or (22 <= day and day < 29):
            return ''
        else:
            week_end_date = currentDate + timedelta(days=1)
    
    week_start_date = week_end_date - timedelta(days=6)

    year = week_start_date.year
    week = week_start_date.strftime("%V")
    d = str(year)+'-'+ week

    excludeList = TimesheetStatus.objects.filter(
        weeknumber = week,
        weekyear=year,
        timesheet_status__in=["Submitted", "Accepted", "Rejected"]
    ).values_list('uid', flat=True)

    data =users.objects.values('first_name','email').annotate(
                                            _reportingto= F('reporting_to__email')
                                            ).exclude(Q(id__in = excludeList)).filter(Q(is_active=True) & ~Q(role__in =["Admin","HR","Consultant","CEO"]))
    
    return JsonResponse({"result":list(data),'year':year,
                         "unFilledEmployeeNames":list(data.values_list('first_name', flat=True)),
                         'week':week ,'week_start_date':week_start_date.date(),'week_end_date':week_end_date.date(),'weekDay':weekday})

#-------------------------------- daily remainder email ------------------------------------
def dailyRemainderEmail(request):
    currentDate = datetime.today()
    yesterday = currentDate - timedelta(days=1)

    try:
        yesterdayList = list(Submission.objects.values_list('assignId__assignTo',flat = True).filter(date = yesterday).distinct()) 
    
        yesterdayNotFilledUsers = users.objects.values('first_name','email').annotate(
                                                _reportingto= F('reporting_to__email')
                                                ).exclude(Q(id__in = yesterdayList)).filter(Q(is_active=True) & ~Q(role__in =["Admin","HR","Consultant","CEO"]))
    except Exception as e:
        logger.exception("Error occurred while processing submission reminder logic.")
        return JsonResponse({"error": "An error occurred while processing the request."}, status=500)

    return JsonResponse({ "yesterdayNotFilledUsers":list(yesterdayNotFilledUsers),
                        'yesterdayDate':yesterday.strftime('%d-%b-%Y')
                            })

def weeklyApprovalMail(request):
    currentDate = datetime.today()
    year = currentDate.year
    week = int(currentDate.strftime("%V"))

    # Calculate week start and end dates
    weekday = currentDate.weekday()

    if weekday == 5:  # Saturday
        day = int(currentDate.strftime('%d'))
        if (8 <= day < 15) or (22 <= day < 29):
            return JsonResponse({"result": [], 'year': year, 'week': week, 'week_start_date': None, 'week_end_date': None})

        week -= 1
        week_start_date = currentDate - timedelta(days=7)
        week_end_date = currentDate - timedelta(days=1)
        year = week_start_date.year

    else:
        day = int((currentDate - timedelta(days=2)).strftime('%d'))
        if (8 <= day < 15) or (22 <= day < 29):
            week -= 2
            week_start_date = currentDate - timedelta(days=10)
            week_end_date = currentDate - timedelta(days=3)
            year = week_start_date.year
        else:
            return JsonResponse({"result": [], 'year': year, 'week': week, 'week_start_date': None, 'week_end_date': None})

    # Fetching users who have not unlocked timesheets
    excludeList = set(
        TimesheetStatus.objects.filter(weeknumber=week, weekyear=year)
        .exclude(timesheet_status="Unlocked")
        .values_list('uid', flat=True)
    )

    notApprovedUsers = list(
        users.objects.filter(is_active=True)
        .exclude(id__in=excludeList)
        .exclude(role__in=["Admin", "HR", "Consultant", "CEO"])
        .values('first_name', 'email')
        .annotate(
            _reportingto=F('reporting_to__email'),
            _reporterName=F('reporting_to__first_name')
        )
    )

    return JsonResponse({
        "result": notApprovedUsers,
        'year': year,
        'week': week,
        'week_start_date': week_start_date.date(),
        'week_end_date': week_end_date.date()
    })
