"""
Admin routes for Lambdah portfolio — paste into your main routes file
or import as a Blueprint.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from portfolio import app, db
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from portfolio.models import BlogPost, BlogComment, Admin, ResumeDownload
import re


# ─────────────────────────────────────────────
# Auth decorator
# ─────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def slugify(text):
    """Convert a string to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


# ─────────────────────────────────────────────
# Login / Logout
# ─────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_id'] = admin.id
            flash('Welcome back!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials.', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_posts     = BlogPost.query.count()
    published_posts = BlogPost.query.filter_by(is_published=True).count()
    pending_comments = BlogComment.query.filter_by(is_approved=False).count()
    total_views     = db.session.query(db.func.sum(BlogPost.views)).scalar() or 0

    posts         = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    recent_posts  = posts[:5]
    comments      = BlogComment.query.order_by(BlogComment.created_at.desc()).all()
    resume_download_count = ResumeDownload.query.count()

    return render_template(
        'admin/dashboard.html',
        total_posts=total_posts,
        published_posts=published_posts,
        pending_comments=pending_comments,
        total_views=total_views,
        posts=posts,
        recent_posts=recent_posts,
        comments=comments,
        resume_download_count=resume_download_count,
    )


# ─────────────────────────────────────────────
# Blog Posts – Create
# ─────────────────────────────────────────────
@app.route('/admin/posts/create', methods=['POST'])
@admin_required
def admin_create_post():
    try:
        title    = request.form.get('title', '').strip()
        slug     = request.form.get('slug', '').strip() or slugify(title)
        excerpt  = request.form.get('excerpt', '').strip()
        content  = request.form.get('content', '').strip()
        image    = request.form.get('featured_image', '').strip()
        category = request.form.get('category', '').strip()
        tags     = request.form.get('tags', '').strip()
        is_pub   = request.form.get('is_published', '1') == '1'

        if not title or not content:
            return jsonify(success=False, message='Title and content are required.')

        # Ensure unique slug
        base_slug = slug
        counter = 1
        while BlogPost.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        post = BlogPost(
            title=title,
            slug=slug,
            excerpt=excerpt or None,
            content=content,
            featured_image=image or None,
            category=category or None,
            tags=tags or None,
            is_published=is_pub,
        )
        db.session.add(post)
        db.session.commit()
        return jsonify(success=True, message='Post created successfully!', post_id=post.id)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))


# ─────────────────────────────────────────────
# Blog Posts – Update
# ─────────────────────────────────────────────
@app.route('/admin/posts/<int:post_id>/update', methods=['POST'])
@admin_required
def admin_update_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    try:
        title    = request.form.get('title', '').strip()
        slug     = request.form.get('slug', '').strip() or slugify(title)
        excerpt  = request.form.get('excerpt', '').strip()
        content  = request.form.get('content', '').strip()
        image    = request.form.get('featured_image', '').strip()
        category = request.form.get('category', '').strip()
        tags     = request.form.get('tags', '').strip()
        is_pub   = request.form.get('is_published', '1') == '1'

        if not title or not content:
            return jsonify(success=False, message='Title and content are required.')

        # Check slug uniqueness (excluding current post)
        existing = BlogPost.query.filter(BlogPost.slug == slug, BlogPost.id != post_id).first()
        if existing:
            slug = f"{slug}-{post_id}"

        post.title          = title
        post.slug           = slug
        post.excerpt        = excerpt or None
        post.content        = content
        post.featured_image = image or None
        post.category       = category or None
        post.tags           = tags or None
        post.is_published   = is_pub
        post.updated_at     = datetime.utcnow()

        db.session.commit()
        return jsonify(success=True, message='Post updated successfully!')

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))


# ─────────────────────────────────────────────
# Blog Posts – Delete
# ─────────────────────────────────────────────
@app.route('/admin/posts/<int:post_id>/delete', methods=['POST'])
@admin_required
def admin_delete_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    try:
        # Delete associated comments first
        BlogComment.query.filter_by(post_id=post_id).delete()
        db.session.delete(post)
        db.session.commit()
        return jsonify(success=True, message='Post deleted.')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))


# ─────────────────────────────────────────────
# Comments – Approve
# ─────────────────────────────────────────────
@app.route('/admin/comments/<int:comment_id>/approve', methods=['POST'])
@admin_required
def admin_approve_comment(comment_id):
    comment = BlogComment.query.get_or_404(comment_id)
    try:
        comment.is_approved = True
        db.session.commit()
        return jsonify(success=True, message='Comment approved.')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))

@app.route('/api/resume-download', methods=['POST'])
def log_resume_download():
    db.session.add(ResumeDownload(downloaded_at=datetime.utcnow()))
    db.session.commit()
    return jsonify(success=True)


# ─────────────────────────────────────────────
# Comments – Delete
# ─────────────────────────────────────────────
@app.route('/admin/comments/<int:comment_id>/delete', methods=['POST'])
@admin_required
def admin_delete_comment(comment_id):
    comment = BlogComment.query.get_or_404(comment_id)
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify(success=True, message='Comment deleted.')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))
