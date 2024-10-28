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
     # Total number of registered books
    total_books = Book.objects.count()
    
    # Total number of purchased books
    total_purchased_books = Purchase.objects.count()
    
    # Total purchase amount in dollars
    total_purchase_amount = Purchase.objects.aggregate(Sum('book__price'))['book__price__sum'] or 0

    # Context data for the template
    context = {
        'total_books': total_books,
        'total_purchased_books': total_purchased_books,
        'total_purchase_amount': total_purchase_amount
    }

    return render(request, "admin_page/dashboard.html", context)


@login_required(redirect_field_name='next', login_url='/admin-login/')
def Add_book(request):
    if request.method == "POST":
        title = request.POST.get("title")
        author = request.POST.get("author")
        category = request.POST.get("category")
        description = request.POST.get("description")
        price = request.POST.get("price")
        published_date = request.POST.get("published_date")
        cover_image = request.POST.get("image_url")

        # Create and save the new book instance
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

        # Show success message
        messages.success(request, "Book added successfully!")

        return redirect("add-book")  # Redirect to the same page or another view

    return render(request, "admin_page/add-book.html")


@login_required(redirect_field_name='next', login_url='/admin-login/')
def display_book(request):

    books = Book.objects.all()  # Fetch all books from the database
    return render(request, "admin_page/display_books.html", {"books": books})

class BookUpdateView(LoginRequiredMixin, UpdateView):
    model = Book
    template_name = "admin_page/update-book.html"
    fields = ["title", "author", "category", "description", "price"]
    success_url = reverse_lazy("display-book")  # Redirect to the book list view or any desired page
    
    # Define the URL to redirect to for unauthenticated users
    login_url = '/admin-login/'  # Custom login URL for unauthorized users

    def form_valid(self, form):
        messages.success(self.request, "Book updated successfully.")
        return super().form_valid(form)

@login_required(redirect_field_name='next', login_url='/admin-login/')
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        book.delete()
        messages.success(request, "Book deleted successfully.")
        return redirect("display-book")
    return render(request, "admin_page/display_books.html", {"book": book})


def stripe_checkout(request, book_id):
    try:
        get_book = get_object_or_404(Book, pk=book_id)

        if get_book.price <= 0:
            return redirect("index")  # Redirect or handle the error accordingly

        book_price_in_cent = int(get_book.price * 100)

        # Create a Stripe Checkout Session
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
            },  # Ensure book_id is a string
            # Collect the customer's email from the Stripe Checkout form
            customer_email=request.POST.get('email'),  # Get email from the request
            billing_address_collection='required',  # Require the customer to provide their address
            phone_number_collection={'enabled': True},  # Enable phone number collection
        )

        return redirect(stripe_session.url)

    except stripe.error.StripeError as e:
        print("Exception: ", e)
        return redirect("index")  # Redirect or handle the error appropriately



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
    # Retrieve book ID from the metadata
    book_id = stripe_session["metadata"].get("book_id")  # Use .get() to avoid KeyError

    # Retrieve user email from the session
    user_email = stripe_session["customer_details"][
        "email"
    ]  # This will be retrieved from Stripe's email field

    if user_email and book_id:  # Ensure both values are present
        # Create the Purchase object
        purchase = Purchase(
            user_email=user_email,
            fullname = stripe_session["customer_details"]["name"],
            phone_number = stripe_session["customer_details"]["phone"],
            address = stripe_session["customer_details"]["address"]["city"],
            zip_code = stripe_session["customer_details"]["address"]["postal_code"],
            book_id=book_id,  # Assuming you have a ForeignKey to Book
        )
        purchase.save()  # Save the Purchase object

        subject = "Purchase Confirmation"
        context = {
            "book_title": stripe_session["metadata"].get("book_title"),
            "book_image": stripe_session["metadata"].get("book_img"),
            "author": stripe_session["metadata"].get("book_author"),
            "price": stripe_session["metadata"].get("book_price"),
        }
        message = render_to_string("admin_page/purchase_email.html", context)

        # Send the email
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user_email],  # Send to the customer's email
            fail_silently=False,
            html_message=message,  # This allows for HTML content
        )
    else:
        # Handle the case where email or book_id is not available
        print("Purchase could not be created. Missing user_email or book_id.")


class PaymentSuccessView(TemplateView):
    template_name = "admin_page/payment-success.html"

    # You can also add context if needed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PaymentCancelView(TemplateView):
    template_name = "admin_page/payment-cancel.html"  # The template to render

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["message"] = "Your payment has been canceled."  # Example context data
        return context

@login_required(login_url='/admin-login/')
def user_logout(request):
    logout(request)
    return redirect('login-page')  # Redirect to login page or any other page after logout