# Demo Images Guide

This guide explains how to add demo screenshots to the repository without mixing the instructions into the main README.

## 1. Create an Image Folder

Create a folder for demo screenshots:

```text
assets/demo/
```

Example structure:

```text
assets/
└── demo/
    ├── chat-demo.png
    └── source-citations.png
```

## 2. Add Screenshots

Recommended screenshots:

- Main chat screen with a student question and chatbot answer.
- Source citation cards below the answer.
- Optional: welcome screen or category selection if useful.

Use `.png` for UI screenshots. Keep each image below a few MB so the repository stays lightweight.

## 3. Reference Images in Markdown

To show the images in any Markdown file, use relative paths:

```md
![Chat demo](assets/demo/chat-demo.png)
![Source citations](assets/demo/source-citations.png)
```

## 4. Safety Checklist

Before committing screenshots, check that they do not expose:

- API keys or `.env` values.
- Private terminal paths if they are not needed.
- Personal account information.
- Sensitive student data.

## 5. Commit the Images

After adding screenshots:

```bash
git add assets/demo DEMO_IMAGES_GUIDE.md
git commit -m "Add demo screenshots"
git push origin main
```
