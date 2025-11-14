"""
views.py

Description: Views for the Timesheet Managment application.

Programmer Details:
- Name: Libina
- Email: libinap@icpro.in
- Date Created: 03-Jun-2024
- Last Modified: [Last Modification Date]
- Version: 2.0

Notes:
- [Any additional notes or comments about the file or its purpose]
"""


from django.shortcuts import render,redirect
from django.contrib.auth import login, authenticate,logout
from django.contrib.auth.models import User,Group

from .models import users,modules,page,PageGroup,Role,JobTitles,OtherPermissions
from .forms import usersForm
from django.contrib.auth.decorators import login_required
from django. views. decorators. csrf import csrf_exempt
from django.contrib import messages
from .decorators import unathenticated,allowedGroups
from django.http.response import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.db.models import F
from django.db import models
# for sending email
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from templates.mailContents import employeeAddedEmailBody,employeeProfileChangedEmailBody
from datetime import date , timedelta,datetime
import json
from django.core.cache import cache



@csrf_exempt
def loginUser(request):
    """
    Authenticate and log in a user based on submitted credentials.

    Parameters:
    - request: The HTTP POST request object containing user credentials.

    Returns:
    - A redirect to the 'index' page if authentication is successful.
    - A redirect to the 'home' page with an error message if authentication fails.
    """
    username = request.POST.get('username')  # Get the username from the POST request
    password = request.POST.get('password')  # Get the password from the POST request

    # Authenticate the user
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        # Log the user in if authentication is successful
        login(request, user)
        return redirect('index')  # Redirect to the index page
    else:
        # Show an error message and redirect to the home page if authentication fails
        messages.error(request, 'Invalid credentials. Please try again.')
        return redirect('home')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@login_required(login_url='home')
def index(request):
    """
    Render the home page for logged-in users.

    Parameters:
    - request: The HTTP request object.

    Returns:
    - A rendered 'home.html' template with the module context set to "home".
    """
    return render(request, 'home.html', {"module": "home"})

@csrf_exempt  # Use with caution, consider removing if CSRF protection is not required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@login_required(login_url='home')
def signup(request):
    """
    Handle the user signup process.

    Parameters:
    - request: The HTTP request object containing user data.

    Returns:
    - Redirects to the 'getUsers' view on successful user creation.
    - JSON response with form errors if the form is invalid.
    """
    if request.method == 'POST':
        form = usersForm(request.POST)
        if form.is_valid():
            role = request.POST.get('role')
            group = request.POST.get('groupfield')

            jobtitleObj, created  = JobTitles.objects.get_or_create(role_id=role,group_id=group)

            # Create user instance but do not save to the database yet
            user = form.save(commit=False)

            # Assign reporting manager if provided
            reporting_to_id = request.POST.get('reporting_to')
            if reporting_to_id:
                try:
                    user.reporting_to = users.objects.get(pk=int(reporting_to_id))
                except users.DoesNotExist:
                    return JsonResponse({"formError": "Reporting manager not found."})
            user.jobtitle = jobtitleObj
            # Save the user instance to the database
            user.save()
            OtherPermissions.objects.get_or_create(jobtitle=jobtitleObj)

            # Send email to the new user and their reporting manager
            # send_new_employee_email(user, reporting_to_id)

            return redirect('getUsers')
        else:
            return JsonResponse({"formError": form.errors.as_json()})

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def employeeDetails(request):
    # if request.user.role != "Employee":
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "User").values_list('page__name',flat=True)
    return render(request, 'employee_details.html',{"module":"usermanagement","pageData":list(pageData)})
    # return HttpResponse("Sorry!! You are not Authorized")

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def editEmployee(request):
    """
    Edit an existing employee's details.

    Parameters:
    - request: The HTTP request object containing POST data to update the employee's details.

    Returns:
    - Redirects to the 'getUsers' view after updating the employee's details.
    """
    if request.method == "POST":
        role = request.POST.get('role')
        group = request.POST.get('groupfield')

        jobtitleObj, created  = JobTitles.objects.get_or_create(role_id=role,group_id=group)

        # Retrieve the user instance
        user = users.objects.get(id=request.POST.get('id'))

        # Update user fields directly from the POST data
        user.first_name = request.POST.get('first_name')
        user.role = role
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.phone = request.POST.get('phone')
        user.designation = request.POST.get('designation')
        user.resigned_date = request.POST.get('resigned_date')
        oldReporter = user.reporting_to.id

        # Handle reporting_to field
        reporting_to_id = int(request.POST.get('reporting_to'))
        user.reporting_to = users.objects.get(pk=reporting_to_id) 

        # Update the is_active status
        user.is_active = request.POST.get('is_active') == "on"
        user.jobtitle = jobtitleObj
        # Save updated fields
        user.save(update_fields = [
            'first_name', 'role', 'username', 'designation', 
            'email', 'reporting_to', 'phone', 'is_active', 'resigned_date', 'jobtitle'
        ])
        OtherPermissions.objects.get_or_create(jobtitle=jobtitleObj)

        if reporting_to_id:
            if oldReporter != reporting_to_id:
                send_changeReporter_email(user,"reporting_to change")
            else:
                # Send email to the new user and their reporting manager
                send_changeReporter_email(user,"profile changed")

        return redirect('getUsers')

@csrf_exempt
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getUsers(request):
    """
    Retrieve a list of users based on their active status and include their group names.

    Parameters:
    - request: The HTTP request object containing the 'checked' parameter to filter active users.

    Returns:
    - A JSON response with user details and their associated groups.
    """
    isActive = True 

    # Check if the request is a POST and adjust the isActive flag
    if request.method == 'POST':
        isActive = request.POST.get('checked') == "true"
        
    # Retrieve users with the specified active status and prefetch related groups
    users_queryset = users.objects.filter(is_active=isActive).select_related('reporting_to')

    if request.user.jobtitle_id != 1:
        users_queryset = users_queryset.exclude(jobtitle_id = 1)
    
    # Serialize the user details and their groups
    user_list = []
    for user in users_queryset:
        user_data = {
            'id': user.id,
            'first_name': user.first_name,
            'username': user.username,
            'designation': user.designation,
            'jobrole': (user.jobtitle.role.name if getattr(user.jobtitle, 'role', None) else None),
            'jobgroup': (user.jobtitle.group.name if getattr(user.jobtitle, 'group', None) else None),
            'jobroleid': (user.jobtitle.role_id if getattr(user.jobtitle, 'role_id', None) else None),
            'jobgroupid': (user.jobtitle.group_id if getattr(user.jobtitle, 'group_id', None) else None),
            'email': user.email,
            'phone': user.phone,
            'is_active': user.is_active,
            'reporting_to':user.reporting_to.id if user.reporting_to else None,
            'reporter_name': user.reporting_to.first_name if user.reporting_to else None,
            'resigned_date':user.resigned_date.strftime('%Y-%m-%d') if user.resigned_date else None
        }
        user_list.append(user_data)
    usersList = list(users.objects.values('id','first_name'))
    groupList = list(Group.objects.values('id','name'))
    roleList = list(Role.objects.values('id','name'))
    return JsonResponse({"users": user_list,"usersList":usersList,"groupList":groupList,'roleList':roleList})

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def deleteEmployee(request):
    if request.method == "POST":
        user_id = request.POST.get('id')
        users.objects.get(id=user_id).delete()
    return redirect('getUsers')

def send_new_employee_email(user, reporting_to_id):
    """
    Send an email notification when a new employee is added.

    Parameters:
    - user: The newly created user instance.
    - reporting_to_id: The ID of the reporting manager.
    """
    subject = 'New Employee Added'
    text_content = "A new employee has been added to the system."
    userName = user.username
    name = user.first_name
    email = user.email
    mobileNo = user.phone
    role = user.role
    designation = user.designation
    reporting_manager = users.objects.filter(pk=reporting_to_id).first()
    
    html_content = employeeAddedEmailBody(reporting_manager.first_name,userName,name,email,mobileNo,role,designation,datetime.today().date())
    msg = EmailMultiAlternatives(subject,text_content,"no-replay@gmail.com",[reporting_manager.email],cc=[email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def send_changeReporter_email(user,change):
    """
    Send an email notification when a employee's reporting manager change is added.

    Parameters:
    - user: The newly reporting manager user instance.
    - reporting_to_id: The ID of the reporting manager.
    """
    reportingManager = user.reporting_to.first_name
    name = user.first_name
    username = user.username
    email = user.email
    mobile = user.phone
    role = user.role
    designation = user.designation

    text_content = "This is an important message."
    if change == "reporting_to change":
        subject = 'Important Update: Change in Reporting Manager'
        message = "you will be taking over as the reporting manager for"
    else:
        subject = 'Important Update: Change in Profile'
        message = "The profile is modified for"
    html_content = employeeProfileChangedEmailBody(reportingManager,message,name,username,email,mobile,reportingManager,role,designation)
    msg = EmailMultiAlternatives(subject,text_content,"icproprojects@gmail.com",[user.reporting_to.email],cc=[user.email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

# usermanagement
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getUserManagementSettings(request):
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "User").values_list('page__name',flat=True)
    return render(request,'userManagementSettings.html',{"module":"usermanagement","pageData":list(pageData)})

@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getUserManagementData(request):
    data = Group.objects.values()
    module_list = modules.objects.values('id','name')
    if request.method == 'POST':
        selectedRadioId = request.POST.get('selectedRadioId')
        tableRowId = request.POST.get('id')
        mode = request.POST.get('mode')
        if selectedRadioId == 'groupRadioButton':
            if mode == 'delete':
                Group.objects.filter(pk=tableRowId).delete()
            elif mode:
                name = request.POST.get('name')
                if not tableRowId:
                    Group.objects.create(name=name)
                else:
                    groupData = Group.objects.get(pk=tableRowId)
                    groupData.name = name
                    groupData.save()
            else:
                ''
            data = Group.objects.values()
        elif selectedRadioId == 'ModuleRadioButton':
            if mode == 'delete':
                modules.objects.filter(pk=tableRowId).delete()
            elif mode:
                name = request.POST.get('name')
                if not tableRowId:
                    modules.objects.create(name=name)
                else:
                    modulesData = modules.objects.get(pk=tableRowId)
                    modulesData.name = name
                    modulesData.save()
            else:
                ''
            data = modules.objects.values()
        elif selectedRadioId == 'roleRadioButton':
            if mode == 'delete':
                Role.objects.filter(pk=tableRowId).delete()
            elif mode:
                name = request.POST.get('name')
                if not tableRowId:
                    Role.objects.create(name=name)
                else:
                    roleData = Role.objects.get(pk=tableRowId)
                    roleData.name = name
                    roleData.save()
            else:
                ''
            data = Role.objects.values()
        else:
            if mode == 'delete':
                page.objects.filter(pk=tableRowId).delete()
            elif mode:
                name = request.POST.get('name')
                module = request.POST.get('moduleId')
                pageurl = request.POST.get('pageurl')
                if not tableRowId:
                    page.objects.create(name=name,module_id=module,pageURL=pageurl)
                else:
                    pageData = page.objects.get(pk=tableRowId)
                    pageData.name = name
                    pageData.module_id = module
                    pageData.pageURL = pageurl
                    pageData.save()
            else:
                ''
            data = page.objects.values('id','name','module__name','module__id','pageURL')
    return JsonResponse({"tableData":list(data),"module_list":list(module_list)})

# userPermission
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def userPermissions(request):
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "User").values_list('page__name',flat=True)
    return render(request,'userPermissions.html',{"module":"usermanagement","pageData":list(pageData)})

@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getUserPermissionsData(request):
    jobTitleData = JobTitles.objects.values('id','group__name','role__name')
    pageData = page.objects.values('id','name','module__name','module__id')
    dailyEmailList = []
    weeklyEmailList = []
    notSubmittedSummaryMailList = []
    otherMailsList = []
    hoursRestrictionList = []
    unlockLongTermList = []
    excludeList = []
    if request.method == 'POST':
        selectedRadio = request.POST.get('selectedRadio')
        checkedData = request.POST.get('checkedData')
        if selectedRadio == 'pagePermissionsButton' : 
            if checkedData:
                checkedList = json.loads(checkedData)
                PageGroup.objects.all().delete()
                for item in checkedList:
                    PageGroup.objects.create(page_id=item['pageId'], jobtitle_id=item['jobTitleId'])
        else:
            weeksCount = request.POST.get('weeksCount')
            if weeksCount:
                cache.set("unlockAllowedWeeks", weeksCount,timeout=None)
                return JsonResponse({"weeksCount":cache.get("unlockAllowedWeeks")})
            else:
                if checkedData:
                    checkedList = json.loads(checkedData)
                    # Get all BooleanField names in the model
                    boolean_fields = [
                        f.name for f in OtherPermissions._meta.get_fields()
                        if isinstance(f, models.BooleanField)
                    ]

                    # Set all to False for that jobtitle
                    OtherPermissions.objects.update(
                        **{field: False for field in boolean_fields}
                    )

                    for item in checkedList:
                        jobTitleId = int(item['jobTitleId'])
                        fieldName = item['fieldName']
                        OtherPermissions.objects.filter(jobtitle_id=jobTitleId).update(**{fieldName: True})
                        if fieldName == "dailyEmail":
                            dailyEmailList.append(jobTitleId)
                        elif fieldName == "weeklyEmail":
                            weeklyEmailList.append(jobTitleId)
                        elif fieldName == "notSubmittedSummaryMail":
                            notSubmittedSummaryMailList.append(jobTitleId)
                        elif fieldName == "hoursRestriction":
                            hoursRestrictionList.append(jobTitleId)
                        else:
                            excludeList.append(jobTitleId)
                    cache.set("dailyEmailList", dailyEmailList,timeout=None)
                    cache.set("weeklyEmailList", weeklyEmailList,timeout=None)
                    cache.set("notSubmittedSummaryMailList", notSubmittedSummaryMailList,timeout=None)
                    cache.set("hoursRestrictionList", hoursRestrictionList,timeout=None)
                    cache.set("excludeList", excludeList,timeout=None)
                
                othersmappings = OtherPermissions.objects.values('id','jobtitle','dailyEmail','weeklyEmail','notSubmittedSummaryMail','hoursRestriction','exclude')
                return JsonResponse({"jobTitleData":list(jobTitleData),"othersmappings":list(othersmappings)})
        # else:
        #     hrEmailRestriction = request.POST.get('hrEmailRestriction')
        #     if hrEmailRestriction:
        #         unlockAllowedWeeks = request.POST.get('unlockAllowedWeeks')
        #         cache.set("unlockAllowedWeeks", unlockAllowedWeeks,timeout=None)
        #         cache.set("hrEmailRestriction", hrEmailRestriction,timeout=None)
        #     return JsonResponse({"unlockAllowedWeeks":cache.get("unlockAllowedWeeks"),"hrEmailRestriction":cache.get("hrEmailRestriction")})
    mappings = PageGroup.objects.values('page','page__name','jobtitle','jobtitle__group__name','jobtitle__role__name')
    return JsonResponse({"jobTitleData":list(jobTitleData),"pageData":list(pageData),"mappings":list(mappings),"weeksCount":cache.get("unlockAllowedWeeks")})

# home page
@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getpermissionList(request):
    if request.method == 'POST':
        moduleName = request.POST.get('moduleName')
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = moduleName).values('page__pageURL').order_by('page__name')[:1]
    return JsonResponse({"pageData":list(pageData)})