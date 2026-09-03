from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory
from datetime import datetime
from flask_mail import Mail, Message
from portfolio import app, db, logger
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
from functools import wraps
from portfolio.models import BlogPost, BlogComment, Admin, ResumeDownload
import os

#import openai
from openai import OpenAI
import re
from claude_helper import claude_ai
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

mail = Mail(app)


from markupsafe import Markup

@app.template_filter('striptags')
def striptags_filter(value):
    """Strip HTML tags from a string."""
    clean = re.sub(r'<[^>]+>', '', str(value))
    return clean.strip()

# Set OpenAI API key
#openai.api_key = app.config.get('OPENAI_API_KEY')
client = OpenAI(api_key=app.config.get('OPENAI_API_KEY'))

# Helper function to create slug from title
def create_slug(title):
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug

# ============================================
# AI BLOG ASSISTANT ROUTES
# ============================================


# Configuration
UPLOAD_FOLDER = 'portfolio/static/uploads/blog'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_blog_image(file):
    """Save uploaded image and return the file path"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{int(datetime.now().timestamp())}.{ext}"
        
        # Save file
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        # Return relative path for database storage
        return f"/static/uploads/blog/{unique_filename}"
    return None


def save_featured_image(request):
    """Returns the image path string or None."""
    file = request.files.get('featured_image')
    if file and file.filename and allowed_file(file.filename):
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return f"/static/uploads/{filename}"
    # Fall back to existing URL if no new file uploaded
    return request.form.get('featured_image_existing') or None
    
    
    
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_username'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated
    
    
@app.route('/admin/login', methods = (["GET", "POST"]))
def admin_login():
    #form = LoginForm()
    if request.method=='GET':
        return render_template('user/admin_login.html')
    else:
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username !="" and password !="":
            admin = db.session.query(Admin).filter(Admin.username==username).first() 
            if admin !=None:
                pwd =admin.password
                if pwd==password:
                    id = admin.admin_id
                    session['admin_username'] = id
                    flash('Login successful! Welcome back.', 'success')
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash('Invalid username or password', "error")
                    return redirect(url_for('admin_login'))
            else:
                flash("Ensure that your login details are correct, or contact admin for access", "error")  
                return redirect(url_for('admin_login'))     
        else:
            flash("You must complete all fields", "error")
            return redirect(url_for("admin_login"))
            

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

    try:
        resume_download_count = ResumeDownload.query.count()
    except Exception as e:
        # Table missing / DB hiccup — never take the whole dashboard down for a counter
        db.session.rollback()
        logger.exception('Could not read resume download count: %s', e)
        resume_download_count = 0

    return render_template(
        'admin/admin_dashboard.html',
        total_posts=total_posts,
        published_posts=published_posts,
        pending_comments=pending_comments,
        total_views=total_views,
        posts=posts,
        recent_posts=recent_posts,
        comments=comments,
        resume_download_count=resume_download_count,
    )


            
@app.route('/api/ai/generate-titles', methods=['POST'])
def generate_titles():
    #Generate blog title suggestions using AI
    try:
        data = request.get_json()
        topic = data.get('topic', '')
        
        if not topic:
            return jsonify({'success': False, 'error': 'Topic is required'}), 400
        
        # NEW SYNTAX for OpenAI 1.0.0+
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Generate 5 engaging, SEO-friendly blog post titles about: {topic}. Make them catchy and professional. Return only the titles, numbered 1-5."
            }],
            max_tokens=200
        )
        
        titles = response.choices[0].message.content.strip()
        
        return jsonify({'success': True, 'titles': titles})
        
    except Exception as e:
        print(f"Error generating titles: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

    

@app.route('/api/ai/generate-outline', methods=['POST'])
def generate_outline():
    #Generate blog post outline using AI
    try:
        data = request.get_json()
        title = data.get('title', '')
        
        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400
        
        # NEW SYNTAX for OpenAI 1.0.0+
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Create a detailed blog post outline for: '{title}'. Include an introduction, 4-5 main sections with subpoints, and a conclusion. Make it structured and comprehensive."
            }],
            max_tokens=500
        )
        
        outline = response.choices[0].message.content.strip()
        
        return jsonify({'success': True, 'outline': outline})
        
    except Exception as e:
        print(f"Error generating outline: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/expand-section', methods=['POST'])
def expand_section():
    #Expand a section of blog post using AI
    try:
        data = request.get_json()
        section = data.get('section', '')
        context = data.get('context', '')
        
        if not section:
            return jsonify({'success': False, 'error': 'Section is required'}), 400
        
        prompt = f"Write a detailed, engaging paragraph about: {section}"
        if context:
            prompt += f"\nContext: {context}"
        
        # NEW SYNTAX for OpenAI 1.0.0+
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": prompt
            }],
            max_tokens=300
        )
        
        content = response.choices[0].message.content.strip()
        
        return jsonify({'success': True, 'content': content})
        
    except Exception as e:
        print(f"Error expanding section: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/improve-content', methods=['POST'])
def improve_content():
    #Improve existing content using AI
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'error': 'Content is required'}), 400
        
        # NEW SYNTAX for OpenAI 1.0.0+
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Improve this text by making it more engaging, clear, and professional while keeping the same meaning:\n\n{content}"
            }],
            max_tokens=500
        )
        
        improved = response.choices[0].message.content.strip()
        
        return jsonify({'success': True, 'improved': improved})
        
    except Exception as e:
        print(f"Error improving content: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
        
    
        
# AI Chat
@app.route('/api/chat', methods=['POST'])
def chat_with_claude():
    """Simple chat endpoint"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Generate response
        response = claude_ai.generate_text(
            prompt=user_message,
            max_tokens=1024,
            system_prompt="You are a helpful assistant for JuchiAfricana website."
        )
        
        return jsonify({
            'success': True,
            'response': response
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Example route: Generate Blog Post
@app.route('/api/generate-blog', methods=['POST'])
def generate_blog():
    """Generate blog post using Claude"""
    try:
        data = request.get_json()
        topic = data.get('topic', '')
        tone = data.get('tone', 'professional')
        word_count = data.get('word_count', 500)
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        # Generate blog content
        blog_data = claude_ai.generate_blog_content(
            topic=topic,
            tone=tone,
            word_count=word_count
        )
        
        return jsonify({
            'success': True,
            'blog': blog_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Example route: Analyze Comment Sentiment
@app.route('/api/analyze-sentiment', methods=['POST'])
def analyze_sentiment():
    """Analyze sentiment of user comments"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Analyze sentiment
        sentiment_data = claude_ai.analyze_sentiment(text)
        
        return jsonify({
            'success': True,
            'sentiment': sentiment_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
        

@app.route('/chat')
def chat_page():
    """Render the chat interface"""
    return render_template('user/chat.html')

# ============================================
# BLOG ROUTES (Keep as they are)
# ============================================

@app.route('/blog')
def blog_list():
    #Display all blog posts
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', None)
    
    query = BlogPost.query.filter_by(is_published=True)
    
    if category:
        query = query.filter_by(category=category)
    
    posts = query.order_by(BlogPost.created_at.desc()).paginate(
        page=page, per_page=9, error_out=False
    )
    
    # Get all categories for filter
    categories = db.session.query(BlogPost.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('user/blog_list.html', 
                         posts=posts,
                         categories=categories,
                         current_category=category,
                         current_year=datetime.now().year,
                         username=session.get('admin_username'))

@app.route('/blog/<slug>')
def blog_detail(slug):
    #Display single blog post
    post = BlogPost.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Increment views
    post.views += 1
    db.session.commit()
    
    # Get related posts (same category)
    related_posts = BlogPost.query.filter(
        BlogPost.category == post.category,
        BlogPost.id != post.id,
        BlogPost.is_published == True
    ).limit(3).all()
    
    # Get approved comments
    comments = BlogComment.query.filter_by(
        post_id=post.id,
        is_approved=True
    ).order_by(BlogComment.created_at.desc()).all()
    
    return render_template('user/blog_details.html',
                         post=post,
                         related_posts=related_posts,
                         comments=comments,
                         current_year=datetime.now().year,
                         username=session.get('admin_username'))


'''
@app.route('/blog/create', methods=['GET', 'POST'])
def blog_create():
    if session.get('admin_username') !=None:
        #Create new blog post with AI assistant
        if request.method == 'POST':
            try:
                data = request.get_json()
                
                title = data.get('title')
                content = data.get('content')
                excerpt = data.get('excerpt', '')
                category = data.get('category', '')
                tags = data.get('tags', '')
                
                if not title or not content:
                    return jsonify({'success': False, 'error': 'Title and content are required'}), 400
                
                # Create slug
                slug = create_slug(title)
                
                # Check if slug exists
                existing = BlogPost.query.filter_by(slug=slug).first()
                if existing:
                    slug = f"{slug}-{int(datetime.now().timestamp())}"
                
                # Create post
                post = BlogPost(
                    title=title,
                    slug=slug,
                    excerpt=excerpt,
                    content=content,
                    category=category,
                    tags=tags,
                    is_published=True
                )
                
                db.session.add(post)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Blog post created successfully!',
                    'slug': slug
                })
                
            except Exception as e:
                db.session.rollback()
                print(f"Error creating post: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        return render_template('user/blog_create.html', current_year=datetime.now().year, username=session.get('admin_username'))
    else:
        flash('You have been logged out successfully.', 'success')
        return redirect(url_for('admin_login'))
        
'''

@app.route('/blog/create', methods=['GET', 'POST'])
#@login_required  # Add your login decorator
def blog_create():
    if session.get('admin_username') !=None:
        if request.method == 'GET':
            return render_template('user/blog_create.html')
        
        if request.method == 'POST':
            try:
                # Get form data
                title = request.form.get('title', '').strip()
                content = request.form.get('content', '').strip()
                excerpt = request.form.get('excerpt', '').strip()
                category = request.form.get('category', '').strip()
                tags = request.form.get('tags', '').strip()
                
                # Validate required fields
                if not title or not content:
                    return jsonify({
                        'success': False,
                        'error': 'Title and content are required'
                    }), 400
                
                # Handle image upload
                featured_image = None
                if 'featured_image' in request.files:
                    file = request.files['featured_image']
                    if file.filename:  # Check if a file was actually selected
                        # Check file size
                        file.seek(0, os.SEEK_END)
                        file_length = file.tell()
                        if file_length > MAX_FILE_SIZE:
                            return jsonify({
                                'success': False,
                                'error': 'Image size must be less than 5MB'
                            }), 400
                        file.seek(0)  # Reset file pointer
                        
                        # Save image
                        featured_image = save_blog_image(file)
                        if not featured_image:
                            return jsonify({
                                'success': False,
                                'error': 'Invalid image format. Allowed: PNG, JPG, JPEG, GIF, WEBP'
                            }), 400
                
                # Generate slug from title
                slug = generate_slug(title)  # You need to implement this function
                
                # Create blog post in database
                new_post = BlogPost(
                    title=title,
                    slug=slug,
                    content=content,
                    excerpt=excerpt,
                    category=category,
                    tags=tags,
                    featured_image=featured_image,
                    author=session.get('admin_username', 'Admin'),
                    created_at=datetime.now()
                )
                
                db.session.add(new_post)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Blog post published successfully!',
                    'slug': slug
                }), 201
                
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
    else:
        flash('You have been logged out successfully.', 'success')
        return redirect(url_for('admin_login'))

# Helper function to generate slug
def generate_slug(title):
    """Generate URL-friendly slug from title"""
    import re
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    
    # Check if slug exists and make it unique
    base_slug = slug
    counter = 1
    while BlogPost.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug

# Optional: Route to delete image when updating/deleting blog post
@app.route('/blog/delete-image', methods=['POST'])
#@login_required
def delete_blog_image():
    if session.get('admin_username') !=None:
        """Delete blog image from filesystem"""
        try:
            image_path = request.json.get('image_path')
            if image_path:
                full_path = os.path.join(app.root_path, image_path.lstrip('/'))
                if os.path.exists(full_path):
                    os.remove(full_path)
                    return jsonify({'success': True}), 200
            return jsonify({'success': False, 'error': 'Image not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    else:
        flash('You have been logged out successfully.', 'success')
        return redirect(url_for('admin_login'))

@app.route('/api/blog/comment', methods=['POST'])
def add_comment():
    #Add comment to blog post
    try:
        data = request.get_json()
        
        post_id = data.get('post_id')
        name = data.get('name')
        email = data.get('email')
        comment_text = data.get('comment')
        
        if not all([post_id, name, email, comment_text]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        # Verify post exists
        post = BlogPost.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        
        comment = BlogComment(
            post_id=post_id,
            name=name,
            email=email,
            comment=comment_text,
            is_approved=False  # Requires manual approval
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Comment submitted! It will appear after approval.'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding comment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
        

# ============================================
# EXISTING ROUTES (Keep all your existing routes)
# ============================================

@app.route('/send-contact', methods=['POST'])
def send_contact():
    try:
        data = request.get_json()
        
        name = data.get('name')
        email = data.get('email')
        subject = data.get('subject')
        message = data.get('message')
        
        msg = Message(
            subject=f"Portfolio Contact: {subject}",
            recipients=['emeka@lambdahsoftwares.dev'],
            reply_to=email
        )
        
        msg.body = f"""
New contact form submission:

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
Sent from your portfolio contact form on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        mail.send(msg)
        
        return jsonify({'success': True, 'message': 'Email sent successfully!'}), 200
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to send email. Please try again.'}), 500

# Portfolio data (keep your existing data)
PROJECTS = [
    {
        'id': 1,
        'title': 'JuchiAfricana',
        'description': 'Your one-stop destination for authentic African food, stylish fashion, premium beauty products, and exceptional event services.',
        'image': 'juchi.png',
        'tags': ['Flask', 'JavaScript', 'PhpMysql'],
        'category': ['fullstack', 'python', 'react'],
        'demo_url': 'https://juchiafricana.com/',
        'code_url': None
    },
    {
        'id': 2,
        'title': 'Human Auxology Charity Foundation',
        'description': 'Human auxology charity foundation do help the people in need especially in remote areas by providing free primary health care, following their Nutrition...',
        'image': 'auxology.png',
        'tags': ['Flask', 'JavaScript', 'Mysql'],
        'category': ['fullstack', 'python'],
        'demo_url': 'https://humanauxologycharity.org',
        'code_url': None
    },
    {
        'id': 3,
        'title': 'Dr Ahmad Zain',
        'description': 'CEO of a thriving group of companies in the logistics sector and Director of Development at Protocolo Company. A passionate educator and thought leader ...',
        'image': 'zain4.png',
        'tags': ['Python', 'Javascript', 'PhpMysql'],
        'category': ['react'],
        'demo_url': 'https://drahmadzain.com/',
        'code_url': None
    }
]

SKILLS = {
    'backend': [
        {'name': 'Python', 'icon': 'fab fa-python', 'color': 'blue-400', 'level': 95},
        {'name': 'Flask', 'icon': 'fas fa-circle', 'color': 'slate-300', 'level': 90},
        {'name': 'MySQL', 'icon': 'fas fa-database', 'color': 'blue-500', 'level': 87},
        {'name': 'Node.js', 'icon': 'fab fa-node', 'color': 'green-500', 'level': 87}
    ],
    'frontend': [
        {'name': 'React.js', 'icon': 'fab fa-react', 'color': 'cyan-400', 'level': 92},
        {'name': 'JavaScript', 'icon': 'fab fa-js-square', 'color': 'yellow-400', 'level': 90},
        {'name': 'HTML5', 'icon': 'fab fa-html5', 'color': 'orange-500', 'level': 95},
        {'name': 'CSS3', 'icon': 'fab fa-css3-alt', 'color': 'blue-500', 'level': 93},
        {'name': 'Bootstrap', 'icon': 'fab fa-bootstrap', 'color': 'purple-500', 'level': 89}
    ],
    'additional': [
        {'name': 'Git/GitHub', 'icon': 'fab fa-git-alt', 'color': 'red-500', 'level': 90},
        {'name': 'RESTful API', 'icon': 'fas fa-plug', 'color': 'green-400', 'level': 88},
        {'name': 'Responsive Design', 'icon': 'fas fa-mobile-alt', 'color': 'pink-400', 'level': 94},
        {'name': 'Problem Solving', 'icon': 'fas fa-lightbulb', 'color': 'yellow-400', 'level': 96}
    ]
}

STATS = [
    {'value': 20, 'label': 'Projects Completed'},
    {'value': 13, 'label': 'Technologies'},
    {'value': 95, 'label': 'Client Satisfaction %'}
]

CONTACT_INFO = {
    'email': 'emeka@lambdah.dev',
    'phone': '+965 978 99323',
    'location': 'Kuwait'
}

@app.route('/base')
def base():
    username = username=session.get('admin_username')
    
    return render_template('user/base.html', username=session.get('admin_username'))

@app.route('/')
def index():
    """Home page route"""
    return render_template('user/index.html', 
                         projects=PROJECTS, 
                         stats=STATS,
                         contact=CONTACT_INFO,
                         current_year=datetime.now().year,
                         username=session.get('admin_username'))

@app.route('/about')
def about():
    """About page route"""
    return render_template('user/about.html', 
                         skills=SKILLS,
                         contact=CONTACT_INFO,
                         current_year=datetime.now().year,
                         username=session.get('admin_username'))

@app.route('/api/contact', methods=['POST'])
def contact_form():
    """Handle contact form submission"""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'email', 'subject', 'message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        print(f"Contact form submission from {data['name']} ({data['email']})")
        print(f"Subject: {data['subject']}")
        print(f"Message: {data['message']}")
        
        return jsonify({
            'success': True, 
            'message': 'Message sent successfully! I\'ll get back to you soon.'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


#New handle for the blog features         
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
        image    = save_featured_image(request)
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
        image    = save_featured_image(request)
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


@app.route('/admin/comments/<int:comment_id>/unapprove', methods=['POST'])
@admin_required
def admin_unapprove_comment(comment_id):
    comment = BlogComment.query.get_or_404(comment_id)
    try:
        comment.is_approved = False
        db.session.commit()
        return jsonify(success=True, message='Comment unapproved.')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))


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



# Admin logout
@app.route('/admin/logout')
def admin_logout():
    # Clear all admin session data
    session.pop('Admin_login', None)
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('admin_login'))


# ─────────────────────────────────────────────
# Resume download + tracking
# ─────────────────────────────────────────────
RESUME_FILENAME = 'Emeka_Joseph_Ijegalu_IT_CV.pdf'


def _record_resume_download():
    """Insert one row into resume_download. Returns True on success."""
    try:
        db.session.add(ResumeDownload(downloaded_at=datetime.utcnow()))
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.exception('Failed to log resume download: %s', e)
        return False


@app.route('/resume/download')
def download_resume():
    """Serve the CV and count the download server-side."""
    _record_resume_download()
    return send_from_directory(
        app.static_folder,
        RESUME_FILENAME,
        as_attachment=True,
        download_name=RESUME_FILENAME,
    )


@app.route('/api/resume-download', methods=['POST'])
def log_resume_download():
    """Kept for older cached copies of script.js that log via fetch()."""
    ok = _record_resume_download()
    return jsonify(success=ok), (200 if ok else 500)
