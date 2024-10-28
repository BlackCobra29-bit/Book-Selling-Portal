from .models import Book, Purchase
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView
from django.conf import settings
from django.db.models import Sum
from django.views.generic import TemplateView
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY


# Create your views here.
def Index(request):

    books = Book.objects.all()  # Fetch all books from the database
    return render(request, "index.html", {"books": books})

def user_login(request):
    # Check if the user is already authenticated
    if request.user.is_authenticated:
        return redirect('add-book')  # Redirect to the add-book page if already logged in

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)  # Log in the user
            return redirect('app-dashboard')  # Redirect to the add-book page
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "admin_page/login.html")  # Render the login template


@login_required(redirect_field_name='next', login_url='/admin-login/')
def dashboard(request):

    undelivered_purchases = Purchase.objects.filter(delivered=False).count()

     # Total number of registered books
    total_books = Book.objects.count()
    
    # Total number of purchased books
    total_purchased_books = Purchase.objects.count()
    
    # Total purchase amount in dollars
    total_purchase_amount = Purchase.objects.aggregate(Sum('book__price'))['book__price__sum'] or 0
    total_purchase_amount = f"{total_purchase_amount:.2f}"

    # Context data for the template
    context = {
        'total_books': total_books,
        'total_purchased_books': total_purchased_books,
        'total_purchase_amount': total_purchase_amount,
        "undelivered_purchases": undelivered_purchases,
    }

    return render(request, "admin_page/dashboard.html", context)


@login_required(redirect_field_name='next', login_url='/admin-login/')
def Add_book(request):

    undelivered_purchases = Purchase.objects.filter(delivered=False).count()
    
    if request.method == "POST":
        title = request.POST.get("title")
        author = request.POST.get("author")
        category = request.POST.get("category")
        description = request.POST.get("description")
        price = request.POST.get("price")
        published_date = request.POST.get("published_date")
        cover_image = request.POST.get("image_url")

        book = Book(
            title=title,
            author=author,
            category=category,
            description=description,
            price=price,
            published_date=published_date,
            cover_image=cover_image,
        )
        book.save()

        messages.success(request, "Book added successfully!")

        return redirect("add-book")

    return render(request, "admin_page/add-book.html", {"undelivered_purchases": undelivered_purchases})


@login_required(redirect_field_name='next', login_url='/admin-login/')
def display_book(request):

    undelivered_purchases = Purchase.objects.filter(delivered=False).count()

    books = Book.objects.all()
    return render(request, "admin_page/display_books.html", {"books": books, "undelivered_purchases": undelivered_purchases})

@login_required(redirect_field_name='next', login_url='/admin-login/')
def purchase_list(request):

    undelivered_purchases = Purchase.objects.filter(delivered=False).count()
    
    all_purchases = Purchase.objects.all()
    
    context = {
        'undelivered_purchases': undelivered_purchases,
        'all_purchases': all_purchases,
    }
    return render(request, "admin_page/display_purchase.html", context)


class BookUpdateView(LoginRequiredMixin, UpdateView):
    model = Book
    template_name = "admin_page/update-book.html"
    fields = ["title", "author", "category", "description", "price"]
    success_url = reverse_lazy("display-book")
    
    login_url = '/admin-login/'

    def form_valid(self, form):
        messages.success(self.request, "Book updated successfully.")
        return super().form_valid(form)

@login_required(redirect_field_name='next', login_url='/admin-login/')
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    
    undelivered_purchases = Purchase.objects.filter(delivered=False).count()

    if request.method == "POST":
        book.delete()
        messages.success(request, "Book deleted successfully.")
        return redirect("display-book")
    return render(request, "admin_page/display_books.html", {"book": book, "undelivered_purchases": undelivered_purchases})


def stripe_checkout(request, book_id):
    try:
        get_book = get_object_or_404(Book, pk=book_id)

        if get_book.price <= 0:
            return redirect("index")

        book_price_in_cent = int(get_book.price * 100)

        stripe_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": book_price_in_cent,
                        "product_data": {
                            "name": get_book.title,
                            "description": get_book.description,
                            "images": [get_book.cover_image],
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=request.build_absolute_uri(reverse("payment-success")),
            cancel_url=request.build_absolute_uri(reverse("payment-cancel")),
            metadata={
                "book_id": str(get_book.id),
                "book_title": str(get_book.title),
                "book_author": str(get_book.author),
                "book_price": str(get_book.price),
                "book_img": str(get_book.cover_image),
            },

            customer_email=request.POST.get('email'),
            billing_address_collection='required',
            phone_number_collection={'enabled': True},
        )

        return redirect(stripe_session.url)

    except stripe.error.StripeError as e:
        print("Exception: ", e)
        return redirect("index")



@require_POST
@csrf_exempt
def webhook_manager(request):
    stripe_payload = request.body.decode("utf-8")
    signature_header = request.META.get("HTTP_STRIPE_SIGNATURE", None)

    if not signature_header:
        return JsonResponse({"error": "Missing signature"}, status=400)

    try:
        stripe_event = stripe.Webhook.construct_event(
            stripe_payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"error": "Invalid signatures"}, status=400)

    if stripe_event["type"] == "checkout.session.completed":
        stripe_session = stripe_event["data"]["object"]
        print(stripe_session)
        manage_checkout_session(stripe_session)

    return JsonResponse({"status": "success"})


def manage_checkout_session(stripe_session):

    book_id = stripe_session["metadata"].get("book_id")

    user_email = stripe_session["customer_details"][
        "email"
    ]

    if user_email and book_id:
        purchase = Purchase(
            user_email=user_email,
            fullname = stripe_session["customer_details"]["name"],
            phone_number = stripe_session["customer_details"]["phone"],
            address = stripe_session["customer_details"]["address"]["city"],
            zip_code = stripe_session["customer_details"]["address"]["postal_code"],
            book_id=book_id,
        )
        purchase.save()

        subject = "Purchase Confirmation"
        context = {
            "book_title": stripe_session["metadata"].get("book_title"),
            "book_image": stripe_session["metadata"].get("book_img"),
            "author": stripe_session["metadata"].get("book_author"),
            "price": stripe_session["metadata"].get("book_price"),
        }
        message = render_to_string("admin_page/purchase_email.html", context)

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user_email],
            fail_silently=False,
            html_message=message,
        )
    else:
        print("Purchase could not be created. Missing user_email or book_id.")


class PaymentSuccessView(TemplateView):
    template_name = "admin_page/payment-success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PaymentCancelView(TemplateView):
    template_name = "admin_page/payment-cancel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["message"] = "Your payment has been canceled."
        return context

@login_required(login_url='/admin-login/')
def user_logout(request):

    logout(request)

    return redirect('login-page')

@login_required(redirect_field_name='next', login_url='/admin-login/')
def mark_as_delivered(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    purchase.delivered = True  # Mark as delivered
    purchase.save()
    messages.success(request, "The book has been marked as delivered.")
    return redirect('purchase-list')