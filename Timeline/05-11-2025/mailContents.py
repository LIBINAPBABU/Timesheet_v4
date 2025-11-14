from django.utils.html import format_html
# Timesheet submission mail body
def submitedEmailBody(reporterName,user,year,week,fromDate,toDate):
    html="""
        <body>
            <p>Dear %s ,<br><br>
            <h4 style="color: rgb(65, 160, 41);">Timesheet Submitted.</h4>
            This email is to inform you that %s's timesheet for the following week has been submitted.
                <br>
                Year:%s , week:%s , Period: %s to %s
                <br><br>
                Best regards,
                <br>
                IC Pro solutions Pvt Ltd.
                </p>
        </body>
    """
    return html%(reporterName,user,year,week,fromDate,toDate)

# Timesheet submission mail body
def unlockedEmailBody(userName,year,week,fromDate,toDate):
    html="""
        <body>
            <p>Dear %s ,<br><br>
            <h4 style="color: rgb(65, 160, 41);">Timesheet Locked.</h4>
            This email is to inform you that your timesheet for the following week has been Unlocked.
                <br>
                Year:%s , week:%s , Period: %s to %s
                <br><br>
                Best regards,
                <br>
                IC Pro solutions Pvt Ltd.
                </p>
        </body>
    """
    return html%(userName,year,week,fromDate,toDate)


def lockedEmailBody(text_content):
    html = f"""
        <html>
            <body>
                <p>{text_content}</p>
                <br><br>
                Best regards,<br>
                IC Pro Solutions Pvt Ltd.
            </body>
        </html>
    """
    return html



# Timesheet rejected by Manager
def rejectedEmailBody(name,reporterName,year,week,fromDate,toDate,project,task,rejectionReason):
    html="""  
        <body>
            <p>Dear %s ,<br><br>
            <h5 style="color: orange;">Timesheet has not accepted.</h5>
            This email is to inform you that your timesheet for the following week has not accepted by %s.
                <br>
                Year:%s , week:%s , Period: %s - %s
                <br>
                <br>
                Project Name: %s
                <br>
                Task Name: %s
                <br>
                Rejection Reason: %s
                <br><br> 
                Best regards,
                <br>
                IC Pro solutions Pvt Ltd.
                </p>
        </body>
    """
    return html%(name,reporterName,year,week,fromDate,toDate,project,task,rejectionReason)

# New Employee added by H.R To [Reporting Manager ,cc Employee]
def employeeAddedEmailBody(managername,userName,name,email,mobileNo,role,designation,fromDate):
    html="""
        <body>
            <p>Dear %s ,<br><br>
            <h5 style="color: rgb(34, 214, 73);">New Employee added.</h5>
            This email is to inform you that a new employee has been added to your team.
                <br>
                Username: %s<br>
                Name: %s<br>
                Email: %s<br>
                Mobile No: %s<br>
                Role: %s<br>
                Designation: %s<br>
                Start Date: %s
                <br><br>
                Best regards,
                <br>
                IC Pro solutions Pvt Ltd.
                </p>
        </body>
    """ 
    return html%(managername,userName,name,email,mobileNo,role,designation,fromDate)

# profile changed by H.R  To [Reporting manager , Employee]
def employeeProfileChangedEmailBody(managername,message,name,username,email,mobile,manager,role,designation):
    html="""
        <body>
            <p>Dear %s ,<br><br>
            <h5 style="color: rgb(43, 30, 235);">Employee Profile Updated.</h5>
            This email is to inform you that,%s :
            <br>
            Name : %s
            <br>
            Username : %s
            <br>
            Email : %s
            <br>
            Mobile No : %s
            <br>
            Reporter Name : %s
            <br>
            Role : %s
            <br>
            Designation : %s
                <br>
                <br><br>
                Best regards,
                <br>
                IC Pro solutions Pvt Ltd.
                </p>
        </body>
    """
    return html%(managername,message,name,username,email,mobile,manager,role,designation)

# Timesheet submission reminder
def reminderMessageBody(employee_name, year, week, from_date, to_date):
    html = f"""
        <body>
            <p>Dear {employee_name},<br><br>
                <strong style="color: orange;">Weekly Timesheet Not Submitted</strong><br><br>
                This is a reminder that you have not submitted your timesheet for the following period:<br>
                <b>Year:</b> {year}<br>
                <b>Week:</b> {week}<br>
                <b>Period:</b> {from_date} to {to_date}<br><br>

                <strong style="color: orange;">What should you do?</strong><br>
                Please ensure that your timesheet is completed and submitted at <a href="https://tsm.icpro.in/">https://tsm.icpro.in/</a>.<br><br>

                Best regards,<br>
                <em>IC Pro Solutions Pvt Ltd</em>
            </p>
        </body>
    """
    return html


# Timesheet approval reminder 
def apprvalReminderMessageBody(name,year,week,fromDate,toDate):
    html="""
            <body>
				<p>Dear %s ,<br><br>
					<h5 style="color: orange;">Timesheet not yet approved.</h5>
					This email is to inform you that your timesheet for the following week has not yet been approved.
					<br><br>
					Year:%s , week:%s , day: %s - %s

					<h5 style="color: orange;">What to do?</h5>
					Please complete and submit these timesheets in TimeEntryBox,at <a href="https://tsm.icpro.in/">https://tsm.icpro.in/</a> 
					
					<h5 style="color: orange;">In case of questions</h5>
					In case this information is not correct,or you have further questions,please contact libinap@icpro.in.
					<br><br>
					Best regards,
                    <br>
					IC Pro solutions Pvt Ltd.
				</p>
            </body>
        """
    return html%(name,year,week,fromDate,toDate)

# Timesheet daily reminder 
def dailyReminderMessageBody(name, date):
    html = f"""
        <body>
            <p>Dear {name},<br><br>
                <h5 style="color: orange;">Timesheet not yet filled</h5>
                This is a reminder that your timesheet for <b>{date}</b> has not been filled.
                <br><br>
                <h5 style="color: orange;">What should you do?</h5>
                Please log your working hours in the timesheet at 
                <a href="https://tsm.icpro.in/">https://tsm.icpro.in/</a>.
                <br><br>
                Best regards,<br>
                IC Pro Solutions Pvt. Ltd.
            </p>
        </body>
    """
    return html


from django.utils.html import format_html, format_html_join
# Timesheet daily reminder 
def dailyReminderMessageBodyForHr(week, week_start_date, week_end_date, users):

# If users is a list of strings
    formatted_users = format_html_join(
        '\n', '<li>{}</li>', ((user,) for user in users)
    )

    html = format_html(
        '''
        <body>
            <p>Dear HR,<br><br>
                <h5 style="color: orange;">List of Employees with Unfinished Timesheets</h5>
                Please note that the following employees' timesheets for the week {} of the period <strong>{}</strong> to <strong>{}</strong> are still pending completion:
                <br><br>
                <ul>
                    {}
                </ul>
                <br><br>
                Best regards,<br>
                IC Pro Solutions Pvt Ltd.
            </p>
        </body>
        ''',
        week, week_start_date, week_end_date, formatted_users
    )
    return html

def UnlockApprovedEmailBody(name, week):
    html = f"""
    <body>
        <p>Dear {name},</p>
        <h5 style="color: green;">Timesheet Unlocked</h5>
        <p>Your timesheet for <b>{week}</b> has been successfully unlocked.</p>

        <h5 style="color: orange;">What should you do?</h5>
        <p>
            Please log your working hours in the timesheet at 
            <a href="https://tsm.icpro.in/">https://tsm.icpro.in/</a>.
        </p>

        <p>Best regards,<br>
        IC Pro Solutions Pvt. Ltd.</p>
    </body>
    """
    return html
