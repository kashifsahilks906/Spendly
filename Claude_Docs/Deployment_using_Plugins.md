# 🚀 Deploy a Flask App to Railway with Claude Code

A clean, step-by-step deployment checklist for deploying a Flask
application to **Railway** using the **Claude Code plugin ecosystem**.

------------------------------------------------------------------------

## 1. Create a Railway Account

Create an account on [Railway](https://railway.app/) before starting the
deployment.

------------------------------------------------------------------------

## 2. Install the Railway CLI

Install the Railway command-line interface globally with npm:

``` bash
npm install -g @railway/cli
```

Verify the installation:

``` bash
railway --version
```

------------------------------------------------------------------------

## 3. Log In to Railway

Authenticate the Railway CLI with your Railway account:

``` bash
railway login
```

Complete the authentication flow in your browser if prompted.

------------------------------------------------------------------------

## 4. Verify Your Railway Identity

Confirm that the CLI is authenticated correctly:

``` bash
railway whoami
```

If this returns your Railway account information, authentication is
working.

------------------------------------------------------------------------

## 5. Add the Railway Skills Marketplace

Inside **Claude Code**, add the Railway skills marketplace:

``` text
/plugin marketplace add railwayapp/railway-skills
```

------------------------------------------------------------------------

## 6. Install the Railway Skill

Install the Railway skill from the marketplace:

``` text
/plugin install railway@railway-skills
```

This gives Claude Code access to the Railway-specific deployment
workflow and guidance.

------------------------------------------------------------------------

## 7. Deploy the Flask Application

Once the Railway CLI and Claude Code Railway skill are configured,
deploy your Flask application to Railway.

> **Goal:** Deploy the Flask app successfully and obtain a **public
> Railway URL** that can be used to access the application.

Use Claude Code with the installed Railway skill to guide and execute
the deployment workflow.

------------------------------------------------------------------------

## ✅ Deployment Checklist

-   [ ] Railway account created
-   [ ] Railway CLI installed
-   [ ] `railway login` completed
-   [ ] `railway whoami` verified
-   [ ] Railway skills marketplace added to Claude Code
-   [ ] Railway skill installed
-   [ ] Flask application deployed
-   [ ] Public Railway URL obtained
-   [ ] Deployed application verified

------------------------------------------------------------------------

## Command Reference

### Railway CLI

``` bash
npm install -g @railway/cli
railway login
railway whoami
```

### Claude Code Plugins

``` text
/plugin marketplace add railwayapp/railway-skills
/plugin install railway@railway-skills
```

------------------------------------------------------------------------

## 🎯 Final Result

Your Flask application should be deployed to **Railway** and accessible
through a **public URL**.
