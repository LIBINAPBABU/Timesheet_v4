from django.shortcuts import render
from Timeline.models import IcproProject,Quotation,CostSpecification,QuotationCost,AssignedQuotation,TimesheetStatus
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.http import HttpResponse, JsonResponse
from django.db.models import Q,F,Sum,Case, When, Value, CharField, Subquery, OuterRef
from Employee.models import PageGroup


# Create your views here.
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getProjectDetails(request):
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Projects").values_list('page__name',flat=True)
    return render(request,'projectsList.html',{"module":"project","pageData":list(pageData)})

def getProjects(request):
    quotations=Quotation.objects.using('erp').values('quotation_no',
                                                    'project__name',
                                                    'quotationcost__cost__name',
                                                    'customer_name')\
                                                    .annotate(bdg_hrs=Sum(F('quotationcost__quantity'))*9)\
                                                    .filter(create_date__gte ='2024-06-01')\
                                                     .exclude(quotation_no__isnull=True) \
                                                     .exclude(bdg_hrs=0) \
                                                        .distinct()
    
    return JsonResponse({"quotations":list(quotations)})