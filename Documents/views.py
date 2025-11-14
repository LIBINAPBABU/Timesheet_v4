import datetime
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse
from django.shortcuts import redirect, render,get_object_or_404
from Timeline.models import QuotationCost, Quotation, Customer#importing Timeline model from Timeline application
from .forms import document_mange_form,feeds_form,lessonlearnt_form,category_form#,lessonlearntForm  #include the class name which u added in forms
from .models import  category_project, document_manage,feeds,lessonlearnt,Suggestion #include the model name which u have added in models.py
from django. views. decorators. csrf import csrf_exempt
from django.views.decorators.cache import cache_control
from django.shortcuts import render
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
from Employee.models import PageGroup

# Documents
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def Document_list(request):
    date = datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d')
    Documents = document_manage.objects.all()
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Document").values_list('page__name',flat=True)
    return render(request,'document_list.html',{'date':date,'Documents':Documents,'module':'document',"pageData":list(pageData)})

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def upload(request): 
    if request.method == 'POST':
        form = document_mange_form(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('Documents')
        else:
            return JsonResponse({form.errors})
    else:
        form = document_mange_form()
    return JsonResponse({"Error":'Failed to upload Documents'})

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)   
def delete_document(request,id):
    document_manage.objects.get(pk = id).delete()
    return redirect('Documents')

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def upload_file(request):
    document_id =request.POST.get('id')
    if request.method == "POST":
        form = document_mange_form(request.POST, request.FILES)
        if form.is_valid():
            form_data = form.save(commit=False)
            form_data.id= request.POST.get('id')
            form_data.save()
            return redirect('Documents')
        else:
            return JsonResponse({form.errors})
    else:
        form = document_mange_form()
    return JsonResponse({"Error":'Failed to upload Documents'})


# ----------------------------------------------------------------------

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def lesson(request):
    # project_=QuotationCost.objects.using('erp').values('quotation__quotation_no','quotation__project__name').filter(quotation__status = 'Confirmed').distinct()
    # project_=Quotation.objects.using('erp').values('quotation_no','project__name') #taking values from project table
    quotation_ids = Quotation.objects.using('erp') \
            .filter(quotation_no__isnull=False,
                     customer_name__isnull =False,
                     status = 'Confirmed') \
            .values('quotation_no') \
            .annotate(latest_id=Max('id')) \
            .values_list('latest_id', flat=True)
    customer_code_subquery = Customer.objects.filter(
                name=OuterRef('customer_name')
            ).values('code')[:1]
    project_ =  Quotation.objects.using('erp') \
            .filter(Q(id__in=quotation_ids)) \
            .select_related('project') \
            .annotate(customer_code=Subquery(customer_code_subquery)) \
            .values('quotation_no', 'project__name', 'custom_project_name','system_name',
                    'customer_name', 'id', 'sale_type', 'status', 'customer_code','quote_date') \
            .order_by('-id')
    category_= category_project.objects.values().all()
    lesson_ = lessonlearnt.objects.all() #taking values from lesson learnt table 
    if request.method=="POST":
        Project_=request.POST.get('Project')
        Category_=request.POST.get('Category')
        if Project_ == 'All_project' and  Category_== 'All_category':
            lesson_ = lessonlearnt.objects.all() #taking values from lesson learnt table 
        elif Project_ != 'All_project' and  Category_== 'All_category':
            lesson_ = lessonlearnt.objects.filter(Project=Project_).all() #taking values from lesson learnt table 
        elif Project_ == 'All_project' and  Category_!= 'All_category':
            lesson_ = lessonlearnt.objects.filter(Category=Category_).all() #taking values from lesson learnt table 
        else:
            lesson_ = lessonlearnt.objects.filter(Project = Project_,Category = Category_).all() #taking values from lesson learnt table 
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Document").values_list('page__name',flat=True)
    return render(request,'lesson.html',{'project_':project_,'lesson_':lesson_,'category_':category_,'module':'document',"pageData":list(pageData)})

# New LessonLearnt Page Adding Page
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def lessonlearnts(request):
    if request.method=="POST":
        form = lessonlearnt_form(request.POST,request.FILES)
        if form.is_valid():
            form.save()
        return redirect('lesson')
    # project_=Quotation.objects.using('erp').values('quotation_no','project__name')
    project_=QuotationCost.objects.using('erp').values('quotation__quotation_no','quotation__project__name').filter(quotation__status = 'Confirmed')
    lessonlearnt_ = lessonlearnt.objects.all() #taking values from lesson learnt table 
    category_=category_project.objects.all().values() #taking values from category table        
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Document").values_list('page__name',flat=True)
    return render(request,'lesson.html',{'project_':project_,'lessonlearnt_':lessonlearnt_,'category_':category_,'module':'document',"pageData":list(pageData)})

# Edit Added LessonLearnt Details
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_lesson(request):
    if request.method == "POST":
        id =  request.POST.get('id')
        lesson_ = lessonlearnt.objects.get(id = id)
        lesson_.Project =  request.POST.get('Project')
        lesson_.Category =  request.POST.get('Category')
        lesson_.Event =  request.POST.get('Event')
        lesson_.Limitations =  request.POST.get('Limitations')
        lesson_.Actions =  request.POST.get('Actions')
        lesson_.Status =  request.POST.get('Status')
        lesson_.Remark =  request.POST.get('Remark')
        lesson_.save(update_fields=['Project','Category','Event','Limitations','Actions','Status','Remark','Suggestion',])
    return redirect('lesson')

# Deleting Added LessonLearnt Details
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_lesson(request,id):
    lessonlearnt.objects.get(pk = id).delete()
    return redirect('lesson')

# Adding New Category Details Page
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def categorys(request):
    if request.method=="POST":
        form = category_form(request.POST)
        if form.is_valid():
            form.save()
    return redirect('lesson')
      
# Delete Added Category Details
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_category(request,id):
    category_project.objects.get(pk = id).delete()
    return redirect('lesson')

# suggestion
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def suggestion(request):
    if request.method == "POST":
        mode = request.POST.get('mode')
        if mode:  # check if 'mode' is in POST data
            suggestionId = request.POST.get('suggestionId')
            sugestionObject = get_object_or_404(Suggestion, pk=suggestionId)
            if mode == 'deleteSuggestion':
                sugestionObject.delete()
                return JsonResponse({'status': 'ok'})
        else:  # if 'mode' is not in POST, create a new suggestion
            suggestion = request.POST.get('suggestion')
            id = request.POST.get('suggestionId')
            if id:
                selectedValue = request.POST.get('suggestionStatusDropdown')
                editedRemarks = request.POST.get('remarks')
                suggestionObject = Suggestion.objects.get(pk=id)
                suggestionObject.suggestions = suggestion
                suggestionObject.suggestion_status = selectedValue
                suggestionObject.remarks = editedRemarks
                suggestionObject.save()
            else:
                suggestionData = Suggestion(
                    uid_id = request.user.id,
                    suggestions = suggestion,
                    suggestion_status = "Open",
                )
                suggestionData.save()
            return redirect('suggestion')

    # Fetching the suggestion data (with proper field names and optimizations)
    data = Suggestion.objects.values('id','uid','uid__first_name', 'suggestions', 'suggestion_status','created_date','remarks')
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Document").values_list('page__name',flat=True)
    return render(request, 'suggestion.html', {'data': list(data), 'module': 'document',"pageData":list(pageData)})
