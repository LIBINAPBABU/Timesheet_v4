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

from .models import users
from .forms import usersForm
from django.contrib.auth.decorators import login_required
from django. views. decorators. csrf import csrf_exempt
from django.contrib import messages
from .decorators import unathenticated,allowedGroups
from django.http.response import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.db.models import F
# for sending email
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from templates.mailContents import employeeAddedEmailBody,employeeProfileChangedEmailBody
from datetime import date , timedelta,datetime

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
            # Create user instance but do not save to the database yet
            user = form.save(commit=False)

            # Assign reporting manager if provided
            reporting_to_id = request.POST.get('reporting_to')
            if reporting_to_id:
                try:
                    user.reporting_to = users.objects.get(pk=int(reporting_to_id))
                except users.DoesNotExist:
                    return JsonResponse({"formError": "Reporting manager not found."})

            # Save the user instance to the database
            user.save()

            # # Assign groups to the user
            # groupnames = request.POST.getlist('group')
            # groups = Group.objects.filter(name__in=groupnames)
            # user.groups.set(groups)  # Use set() to replace existing groups

            # Send email to the new user and their reporting manager
            send_new_employee_email(user, reporting_to_id)

            return redirect('getUsers')
        else:
            return JsonResponse({"formError": form.errors.as_json()})

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
# @allowedGroups(allowedgroup=['Admin','Software'])
def employeeDetails(request):
    if request.user.role != "Employee":
        return render(request, 'employee_details.html',{"module":"usermanagement"})
    return HttpResponse("Sorry!! You are not Authorized")

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
        # Retrieve the user instance
        user = users.objects.get(id=request.POST.get('id'))

        # Update user fields directly from the POST data
        user.first_name = request.POST.get('first_name')
        user.role = request.POST.get('role')
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

        # Save updated fields
        user.save(update_fields=[
            'first_name', 'role', 'username', 'designation', 
            'email', 'reporting_to', 'phone', 'is_active', 'resigned_date'
        ])

        # # Update user groups
        # user.groups.clear()
        # groupnames = request.POST.getlist('group')
        # groups = Group.objects.filter(name__in=groupnames)
        # user.groups.add(*groups)

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
    # .prefetch_related('groups')

    if request.user.role == "HR":
        users_queryset = users_queryset.exclude(role = "Admin")
    
    # Serialize the user details and their groups
    user_list = []
    for user in users_queryset:
        user_data = {
            'id': user.id,
            'first_name': user.first_name,
            'username': user.username,
            'designation': user.designation,
            'role': user.role,
            'email': user.email,
            'phone': user.phone,
            'is_active': user.is_active,
            'reporting_to':user.reporting_to.id if user.reporting_to else None,
            'reporter_name': user.reporting_to.first_name if user.reporting_to else None,
            'resigned_date':user.resigned_date.strftime('%Y-%m-%d') if user.resigned_date else None
        }
        user_list.append(user_data)
    usersList = list(users.objects.filter(is_active=True).values('id','first_name'))
    return JsonResponse({"users": user_list, "usersList": usersList})

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
    

    # # Prepare HTML content for the email
    # html_content = (
    #     f"Hello {reporting_manager.first_name if reporting_manager else 'Manager'},<br>"
    #     f"A new employee, {user.first_name}, has been added to the system.<br>"
    #     f"Role: {user.role}<br>"
    #     f"Designation: {user.designation}<br>"
    #     f"Date: {datetime.today().date()}<br>"
    #     "Best regards,<br>Your Company"
    # )

    
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