from flask import Flask, render_template, redirect, url_for, flash,abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] =os.environ.get("MY_SECRECT_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# initialize
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB (updated database from local to external using postgresql, add 2nd argument incase we need to run locally using sqlite)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    '''this callback will take the str ID of a user, and return the corresponding user object.'''
    return User.query.get(user_id)

##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # add user id column that referencing the User table
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    # author is object of User Class => post.author = User object
    author = relationship("User", back_populates= "blog_posts")
    # list of comment objects
    comments = relationship("Comment", back_populates = "blog_post")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    
class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key = True)
    email = db.Column(db.String(250), nullable = False, unique = True)
    password = db.Column(db.String(250),nullable = False)
    name = db.Column(db.String(250),nullable = False)
    # user has a collection of BlogPost object ， e.g. one user can have many posts
    blog_posts = relationship("BlogPost", back_populates= "author")
    # one to many relationship between User Table and Comment Table, where one User is linked to many Comment objects
    comments = relationship("Comment", back_populates = "comment_author")

class Comment(db.Model):
    __tablename__= "comments"
    id = db.Column(db.Integer, primary_key = True)
    # connect with user table
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    comment_author = relationship("User", back_populates = "comments")
    # connect with blog_posts table
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    blog_post = relationship("BlogPost", back_populates = "comments" )
    text = db.Column(db.Text, nullable = False)


with app.app_context():
    db.create_all()


#Create decorator that only admin can access certain webpage
def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.id == 1:
            return f(*args, **kwargs)
        return abort(403)
    return wrapper



@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts,logged_in = current_user.is_authenticated)


@app.route('/register', methods=["GET","POST"])
def register():
    form  = RegisterForm()
   
    
    if form.validate_on_submit():

        email = form.email.data
        user = User.query.filter_by(email = email).first()
        # if user exist
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))


        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email = form.email.data,
            password = hash_and_salted_password,
            name = form.name.data
        )

        
        # add new user to db
        db.session.add(new_user)
        db.session.commit()
         #This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)


@app.route('/login', methods = ["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        # find user info in db by email
        user = User.query.filter_by(email =email ).first()

        if not user:
            flash("That email dose not exist, please try again!")
            return redirect(url_for("login")) 
        elif not check_password_hash(user.password, password):
            flash("Password incorrect, please try again!")
            return redirect(url_for("login")) 
        # user exist and password correct:
        else: 
             #This line will authenticate the user with Flask-Login
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form = form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET","POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    

    if form.validate_on_submit() :
        if current_user.is_authenticated:
            
            # add comment to db
            new_comment = Comment(
                user_id = current_user.id,
                comment_author = current_user,
                post_id = post_id,
                blog_post = requested_post,
                text=form.comment.data
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You need to login or register to comment!")
            return redirect(url_for("login"))
    return render_template("post.html", form = form , post=requested_post)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            # after create the relationship betweem 2 tables, the author column now is object of User table that has many user properties. e.g.name,....
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            user_id = current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>",methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=current_user,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
