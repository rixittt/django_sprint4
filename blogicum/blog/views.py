from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import UpdateView

from .forms import (
    UserRegisterForm,
    ProfileEditForm,
    PostCreateForm,
    CommentForm
)
from .models import Post, Comment, Category
from django.utils import timezone


def create_pagination(query_set, page_number):
    paginator = Paginator(query_set, 10)
    page_obj = paginator.get_page(page_number)
    return page_obj


def index(request):
    last_posts = Post.objects.select_related('category').filter(
        pub_date__lte=timezone.now(),
        is_published=True,
        category__is_published=True
    ).order_by('-pub_date')

    page_obj = create_pagination(last_posts, request.GET.get('page'))
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def post_detail(request, pk):
    post = Post.objects.select_related('category').filter(
        Q(is_published=True) | Q(author=request.user),
        Q(category__is_published=True) | Q(author=request.user),
        Q(pub_date__lte=timezone.now()) | Q(author=request.user),
        pk=pk,
    ).first()
    if not post:
        raise Http404()
    form = CommentForm()
    comments = Comment.objects.filter(post=post).order_by('created_at')
    return render(
        request,
        'blog/detail.html',
        {'post': post, 'form': form, 'comments': comments}
    )


def category_posts(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    if not category.is_published:
        raise Http404()
    category_queryset = Post.objects.select_related('category').filter(
        pub_date__lte=timezone.now(),
        is_published=True,
        category__is_published=True,
        category__slug=category_slug,
    ).order_by('-pub_date')
    page_obj = create_pagination(category_queryset, request.GET.get('page'))
    return render(
        request,
        'blog/category.html',
        {'category': category, 'page_obj': page_obj}
    )


class RegisterUser(View):
    def get(self, request):
        form = UserRegisterForm()
        return render(
            request,
            'registration/registration_form.html',
            {'form': form}
        )

    def post(self, request):
        form = UserRegisterForm(data=request.POST)
        if form.is_valid():
            form.save()
            form.login_new_user(request)
            return redirect('blog:index')
        return render(
            request,
            'registration/registration_form.html',
            {'form': form}
        )


def profile(request, username):
    user = get_object_or_404(User, username=username)
    user_posts = Post.objects.filter(author=user).order_by('-pub_date')
    page_obj = create_pagination(user_posts, request.GET.get('page'))
    return render(
        request,
        'blog/profile.html',
        {'profile': user, 'page_obj': page_obj}
    )


@method_decorator(login_required, name='dispatch')
class ProfileEditView(UpdateView):
    model = User
    form_class = ProfileEditForm
    template_name = 'blog/user.html'
    success_url = reverse_lazy('blog:index')

    def get_object(self):
        return self.request.user


@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostCreateForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            if post.pub_date and post.pub_date > timezone.now():
                post.is_published = False
            post.save()
            return redirect(
                'blog:profile',
                username=request.user.username
            )
    else:
        form = PostCreateForm()
    return render(request, 'blog/create.html', {'form': form})


@method_decorator(login_required, name='dispatch')
class PostUpdateView(UpdateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'blog/create.html'

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()

        if post.author != request.user:
            return redirect('blog:post_detail', post.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.object.pk])


@login_required
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        return HttpResponseForbidden()
    if request.method == 'GET':
        form = PostCreateForm(instance=post)
        return render(request, 'blog/create.html', {'form': form})
    post.delete()
    return redirect(reverse('blog:profile', args=[request.user.username]))


@login_required
def add_comment(request, id):
    post = get_object_or_404(Post, pk=id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
    return redirect('blog:post_detail', pk=post.pk)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.author:
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            comment.save()
            return redirect('blog:post_detail', pk=post_id)
    else:
        form = CommentForm(instance=comment)
    return render(
        request,
        'blog/comment.html',
        {'form': form, 'comment': comment}
    )


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.author:
        return HttpResponseForbidden()
    if request.method == 'GET':
        return render(request, 'blog/comment.html', {'comment': comment})
    comment.delete()
    return redirect('blog:post_detail', pk=post_id)
