from __future__ import annotations

import re
import json

# central ads configuration
ADS_CLIENT_ID = "ca-pub-1234567890123456"  # Replace with actual client ID

# Supported formats
IMAGE_FORMATS = ["jpg", "jpeg", "png", "webp", "bmp", "tiff", "gif", "heic", "avif", "svg"]
VIDEO_FORMATS = ["mp4", "webm", "gif"]

# Popular dimensions
POPULAR_DIMENSIONS = [
    {"width": 1080, "height": 1080, "name": "Instagram Square"},
    {"width": 1920, "height": 1080, "name": "YouTube Thumbnail / Full HD"},
    {"width": 1280, "height": 720, "name": "Standard HD Landscape"},
    {"width": 1200, "height": 630, "name": "Open Graph Image (Facebook/LinkedIn)"},
    {"width": 1200, "height": 628, "name": "LinkedIn Shared Image"},
    {"width": 512, "height": 512, "name": "Profile Picture / App Icon"},
    {"width": 1080, "height": 1350, "name": "Instagram Portrait"},
    {"width": 1080, "height": 1920, "name": "Instagram Story / TikTok Vertical"},
    {"width": 800, "height": 800, "name": "Shopify Product Image"},
    {"width": 851, "height": 315, "name": "Facebook Cover Photo"},
    {"width": 1200, "height": 1200, "name": "WordPress Square Block"}
]

# Platforms Configuration
PLATFORM_PRESETS = {
    "instagram": {
        "name": "Instagram",
        "description": "Instagram is highly visual, demanding perfectly cropped creatives to maximize audience engagement.",
        "sizes": [
            {"width": 1080, "height": 1080, "label": "Square Post (1:1)"},
            {"width": 1080, "height": 1350, "label": "Portrait Post (4:5)"},
            {"width": 1080, "height": 566, "label": "Landscape Post (16:9)"},
            {"width": 1080, "height": 1920, "label": "Story & Reels (9:16)"}
        ],
        "mistakes": "Avoid uploading low-resolution images under 320px wide or using non-supported aspect ratios, which causes Instagram to compress and distort images heavily.",
        "best_practice": "Save images in high-quality JPG or PNG format. Keep files under 8MB and match the target aspect ratios exactly."
    },
    "facebook": {
        "name": "Facebook",
        "description": "Facebook serves diverse banner standards across feed updates, event banners, and advertisements.",
        "sizes": [
            {"width": 1200, "height": 630, "label": "Shared Post Image"},
            {"width": 851, "height": 315, "label": "Cover Photo"},
            {"width": 1200, "height": 1200, "label": "Carousel Ad (1:1)"},
            {"width": 1920, "height": 1080, "label": "Event Header Banner"}
        ],
        "mistakes": "Using text-heavy covers or forgetting that mobile cover photo viewable area is narrower than desktop.",
        "best_practice": "Use standard PNG files for graphics containing text or logos to avoid compression artifacts."
    },
    "whatsapp": {
        "name": "WhatsApp",
        "description": "WhatsApp compresses profile photos and status updates dramatically to conserve data bandwidth.",
        "sizes": [
            {"width": 640, "height": 640, "label": "Profile Picture (1:1)"},
            {"width": 1080, "height": 1920, "label": "Status Update (9:16)"},
            {"width": 800, "height": 500, "label": "Shared Link Preview"}
        ],
        "mistakes": "Sending high-res banner layouts with tiny fonts, which become unreadable under WhatsApp's strict compression algorithm.",
        "best_practice": "To reduce compression damage, share images as document attachments or resize them to exact dimensions before uploading."
    },
    "linkedin": {
        "name": "LinkedIn",
        "description": "Professional networks require crisp corporate branding, cover dimensions, and marketing images.",
        "sizes": [
            {"width": 1200, "height": 628, "label": "Shared Image / Ad"},
            {"width": 1584, "height": 396, "label": "Personal Profile Cover"},
            {"width": 1128, "height": 191, "label": "Company Page Banner"},
            {"width": 400, "height": 400, "label": "Company Logo / Avatar"}
        ],
        "mistakes": "Uploading off-center cover pictures where profile photos overlay and block key textual information.",
        "best_practice": "Leave a 30% margin on the left side of cover designs to accommodate corporate logo overlays."
    },
    "youtube": {
        "name": "YouTube",
        "description": "YouTube thumbnails directly decide click-through rates (CTR). Banners must render cleanly on TVs, tablets, and phones.",
        "sizes": [
            {"width": 1280, "height": 720, "label": "Video Thumbnail (16:9)"},
            {"width": 2560, "height": 1440, "label": "Channel Banner Cover"},
            {"width": 800, "height": 800, "label": "Channel Profile Icon"},
            {"width": 150, "height": 150, "label": "Video Watermark"}
        ],
        "mistakes": "Uploading thumbnails above 2MB, which fails YouTube's upload system, or placing crucial text in the bottom right corner where the video length timestamp overlays it.",
        "best_practice": "Keep thumbnails under 2MB. Use high contrast, and place focal subjects and titles on the left or middle of the frame."
    },
    "x": {
        "name": "X (formerly Twitter)",
        "description": "X timeline images display dynamically based on card setups, and headers crop differently on desktop vs mobile.",
        "sizes": [
            {"width": 1200, "height": 675, "label": "Timeline Shared Image (16:9)"},
            {"width": 1500, "height": 500, "label": "Header Banner"},
            {"width": 400, "height": 400, "label": "Profile Photo"}
        ],
        "mistakes": "Ignoring the header safe zones, which leads to head crops or logo overlaps on smaller screen viewports.",
        "best_practice": "Export X headers in JPG format, and keep important graphical elements focused within center margins."
    },
    "pinterest": {
        "name": "Pinterest",
        "description": "Pinterest feeds are structured as vertical boards, requiring tall portrait ratios to capture visual attention.",
        "sizes": [
            {"width": 1000, "height": 1500, "label": "Standard Pin (2:3)"},
            {"width": 1080, "height": 1920, "label": "Story Pin (9:16)"},
            {"width": 1000, "height": 1000, "label": "Square Pin (1:1)"}
        ],
        "mistakes": "Using wide landscape layouts which get scaled down to tiny previews on Pinterest's vertical columns.",
        "best_practice": "Use a 2:3 vertical aspect ratio, add brief bold headline text on the image, and save in high-fidelity PNG."
    }
}

# File Size presets
FILE_SIZE_PRESETS = [20, 50, 100, 200, 500]

# Use cases presets
USE_CASES = {
    "passport-photo": {
        "name": "Passport Photo",
        "width": 600,
        "height": 600,
        "advice": "Passport photos require an exact square aspect ratio (commonly 2x2 inches, which translates to 600x600 pixels at 300 DPI). The background must be solid off-white or plain white with no shadows."
    },
    "cv-upload": {
        "name": "CV Upload",
        "width": 300,
        "height": 300,
        "advice": "Job portals restrict CV profile pictures to clean, small sizes. A professional square headshot (e.g. 300x300 pixels or 400x400 pixels) in a compressed format ensures quick loading for recruiters."
    },
    "job-application": {
        "name": "Job Application Photo",
        "width": 400,
        "height": 500,
        "advice": "Job boards prefer small, standardized sizes. Maintain a clean corporate portrait (aspect ratio 4:5 or 3:4) to fit profile cards without crop distortion."
    },
    "email": {
        "name": "Email Newsletter Banner",
        "width": 600,
        "height": 300,
        "advice": "Email clients load heavy images slowly. An email banner width should be locked to 600px, and compressed heavily (under 100KB) to load instantly for subscribers."
    },
    "website": {
        "name": "Website Banner Hero",
        "width": 1200,
        "height": 630,
        "advice": "Website headers require the perfect balance of visual quality and rapid load speed. Compress hero banners under 150KB and serve them in modern formats like WEBP."
    },
    "shopify": {
        "name": "Shopify Product Thumbnail",
        "width": 800,
        "height": 800,
        "advice": "Shopify recommends square product photos (800x800px or 1024x1024px) for automatic zoom functionality. Compressing product catalogs speeds up e-commerce conversions."
    },
    "wordpress": {
        "name": "WordPress Featured Image",
        "width": 1200,
        "height": 675,
        "advice": "WordPress templates look best when featured article images share a standard 16:9 ratio. Optimizing image metadata boosts blog post speed and page rank."
    }
}

# Blog articles dataset
BLOG_ARTICLES = {
    "jpg-vs-png": {
        "title": "JPG vs PNG: When to Use Which Image Format",
        "summary": "Learn the core differences between JPG (lossy compression) and PNG (lossless transparency) to select the perfect format for website speed.",
        "reading_time": "5 min read",
        "date": "July 8, 2026",
        "category": "Format Guides",
        "content": """
<h2>Understanding JPG and PNG</h2>
<p>Choosing the wrong file format is one of the most common mistakes in web design and development. The choice you make directly impacts your page weight, browser loading speed, and visual presentation. If you serve heavy, uncompressed assets, your visitors will experience slow rendering, leading to higher bounce rates. In this comprehensive guide, we analyze the technical mechanics of JPEG (JPG) and Portable Network Graphics (PNG) to help you decide when to use each format.</p>

<h3>What is JPG (Joint Photographic Experts Group)?</h3>
<p>JPG is a lossy compression format developed in 1992. It is engineered specifically for photographs and continuous-tone images. The lossy compression algorithm works by analyzing the image grid and discarding data that the human visual system is less sensitive to (such as slight shifts in color hue). It uses Discrete Cosine Transform (DCT) mathematical operations to divide the image into 8x8 blocks, compressing details within those blocks.</p>
<p>When you compress a JPEG, you can select the quality level on a scale from 1 to 100. Lowering the quality to around 80-85% can decrease the file size by up to 70% with almost no visible loss in details. However, compressing too heavily introduces visual artifacts, such as blockiness, color bleeding, and ringing noise around sharp edges.</p>
<ul>
  <li><strong>Best for:</strong> Photographic images, product catalogs, landscapes, and graphics with complex gradients.</li>
  <li><strong>Pros:</strong> Excellent compression ratios, highly adjustable file sizes, and universal support on every device and browser.</li>
  <li><strong>Cons:</strong> Lossy nature means editing and resaving degrades quality over time; does not support transparent layers.</li>
</ul>

<h3>What is PNG (Portable Network Graphics)?</h3>
<p>PNG was created in 1996 as an open-source successor to the patented GIF format. Unlike JPG, PNG uses a lossless compression algorithm based on the DEFLATE method (similar to ZIP archiving). This means that when a PNG is compressed, not a single pixel of data is lost or altered. The file can be decompressed and re-rendered with 100% fidelity to the original design.</p>
<p>Furthermore, PNG supports alpha transparency (RGBA), allowing pixels to be semi-transparent or fully transparent. This makes PNG the default choice for graphic elements that need to blend seamlessly with various colored page headers or dark mode backgrounds.</p>
<ul>
  <li><strong>Best for:</strong> Brand logos, UI icons, SaaS dashboard screenshots, charts, and illustrations containing text.</li>
  <li><strong>Pros:</strong> Pixel-perfect rendering, full support for transparent backgrounds, and sharp lines for typography.</li>
  <li><strong>Cons:</strong> File sizes are much larger than JPEGs for photographic content, making them heavy for mobile networks.</li>
</ul>

<h3>Quick Format Decision Guide</h3>
<table>
  <thead>
    <tr>
      <th>Content Type</th>
      <th>Recommended Format</th>
      <th>Key Reason</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Product Showcase Photo</td>
      <td>JPG (or WebP)</td>
      <td>Requires small file sizes, transparency is not needed.</td>
    </tr>
    <tr>
      <td>Corporate Header Logo</td>
      <td>PNG</td>
      <td>Needs transparency to blend into website headers.</td>
    </tr>
    <tr>
      <td>SaaS UI Screenshot</td>
      <td>PNG</td>
      <td>Contains fine text details that must remain crisp.</td>
    </tr>
    <tr>
      <td>Blog Article Featured Image</td>
      <td>JPG (or WebP)</td>
      <td>Photographic header needs to load fast for LCP.</td>
    </tr>
  </tbody>
</table>

<h3>Technical Comparison: Compression and Performance</h3>
<p>Because PNG is lossless, a 1920x1080 resolution photograph saved as a PNG can easily weigh 2MB or more. The same photograph saved as a JPG with 82% quality will weigh around 250KB—nearly a 90% reduction in weight. For a website featuring dozens of images, this difference is massive. A website serving raw PNGs instead of JPEGs will load slowly, causing Google's Core Web Vitals audit to penalize the domain, hurting your organic SEO rankings.</p>
        """
    },
    "webp-vs-avif": {
        "title": "WebP vs AVIF: The Battle of Modern Web Formats",
        "summary": "An in-depth analysis of next-generation formats. Compare WebP and AVIF to optimize your website for maximum Core Web Vitals.",
        "reading_time": "5 min read",
        "date": "July 9, 2026",
        "category": "Performance",
        "content": """
<h2>Next-Gen Formats: WebP vs AVIF</h2>
<p>To rank in Google search results, your web pages must render almost instantly. Google's speed audit, PageSpeed Insights, flags traditional image formats like JPEG and PNG as outdated and recommends converting them to next-generation formats. The two primary modern formats are WebP and AVIF. In this guide, we break down their underlying technology, compression ratios, browser compatibility, and implementation strategies.</p>

<h3>WebP: The Established Modern Standard</h3>
<p>Developed by Google and released in 2010, WebP was designed to replace both JPEG and PNG on the web. It uses a compression algorithm derived from the VP8 video codec's keyframes. WebP is highly versatile because it supports both lossy and lossless compression, alpha channel transparency, and animations (making it a replacement for GIFs as well).</p>
<p>According to comparative studies, WebP lossy images are 25% to 34% smaller than equivalent JPEGs, and WebP lossless images are 26% smaller than equivalent PNGs. This reduction helps web developers maintain pixel clarity while saving valuable server bandwidth.</p>
<ul>
  <li><strong>Compression Ratio:</strong> ~30% smaller than JPEG on average.</li>
  <li><strong>Browser Support:</strong> Universal (97%+ browser coverage across Chrome, Safari, Firefox, Edge, and mobile browsers).</li>
  <li><strong>Best for:</strong> General web images, banners, and simple illustrations.</li>
</ul>

<h3>AVIF: The Future of Aggressive Compression</h3>
<p>AVIF (AV1 Image File Format) is an open-source format finalized in 2019 by the Alliance for Open Media. It is derived from the AV1 video codec's intra-frame compression rules. AVIF represents a major leap in compression efficiency, offering far better results than WebP and JPEG under heavy compression constraints.</p>
<p>AVIF handles detailed textures, gradients, and high-frequency edges exceptionally well, avoiding the blocky artifacts and color smearing that WebP can sometimes produce at lower quality levels. AVIF file sizes are typically 50% smaller than JPEG and 20% smaller than WebP.</p>
<ul>
  <li><strong>Compression Ratio:</strong> ~50% smaller than JPEG, and ~20% smaller than WebP.</li>
  <li><strong>Browser Support:</strong> Widely supported in Google Chrome, Mozilla Firefox, Apple Safari (iOS 16+), and Microsoft Edge.</li>
  <li><strong>Best for:</strong> High-traffic landing page heroes, catalog grids, and photography portfolios.</li>
</ul>

<h3>How to Implement Next-Gen Formats Safely</h3>
<p>While AVIF offers superior compression, some legacy browsers (like old iOS Safari versions or older desktop environments) might fail to parse it. To ensure all users see your content, use the HTML5 <code>&lt;picture&gt;</code> element to provide fallback options. The browser will evaluate the sources in order and render the first format it supports:</p>
<pre><code>&lt;picture&gt;
  &lt;source srcset="hero.avif" type="image/avif"&gt;
  &lt;source srcset="hero.webp" type="image/webp"&gt;
  &lt;img src="hero.jpg" alt="Hero Banner" loading="lazy"&gt;
&lt;/picture&gt;</code></pre>
<p>By implementing this fallback structure, you serve highly optimized AVIF files to modern browsers, WebP to compatible mid-range browsers, and standard JPEGs to legacy devices. This strategy balances compatibility with optimal performance, improving your Largest Contentful Paint (LCP) score.</p>
        """
    },
    "why-whatsapp-reduces-image-quality": {
        "title": "Why Does WhatsApp Reduce Image Quality and How to Avoid It?",
        "summary": "Discover why social networks compress your images, and learn a simple trick to send high-resolution files without losing quality.",
        "reading_time": "4 min read",
        "date": "July 10, 2026",
        "category": "Social Media",
        "content": """
<h2>WhatsApp's Compression Algorithm Explained</h2>
<p>Have you ever taken a beautiful, sharp photo on your phone, sent it to a friend over WhatsApp, only for them to receive a blurry, low-resolution version? This is a common issue for users sharing high-quality designs, product photos, or travel memories. In this article, we explain the technical reasons behind WhatsApp's aggressive compression and share simple techniques to bypass it.</p>

<h3>The Reason: Bandwidth Conservation</h3>
<p>WhatsApp has over 2 billion active users globally, processing billions of media transfers daily. To keep message delivery speeds fast and minimize database load, WhatsApp uses automated background compression. When you send a photo through the standard gallery attach mode, the app applies three major optimizations:</p>
<ol>
  <li><strong>Dimension Downscaling:</strong> If the original image is large (such as 4000x3000 pixels), WhatsApp automatically scales it down, usually capping the longest edge at 1600 pixels.</li>
  <li><strong>Lossy Encoding:</strong> It compresses the JPEG quality level down to roughly 70-80%, introducing visible block artifacts in gradients and fine details.</li>
  <li><strong>Metadata Stripping:</strong> The app removes EXIF metadata (camera model, GPS coordinates, date, and color profile tags) to save extra bytes.</li>
</ol>
<p>While this compression speeds up delivery under weak network conditions, it ruins detailed text, professional layouts, and high-fidelity photographs.</p>

<h3>How to Send High-Resolution Files Without Loss</h3>
<p>If you need to share original, pixel-perfect images with clients, friends, or print shops, you can use these methods to bypass WhatsApp's compression:</p>

<h4>Method 1: Send as a Document (The Best Bypass)</h4>
<p>This is the most reliable workaround. Instead of attaching the photo via the 'Gallery' or 'Camera' option, follow these steps:</p>
<ol>
  <li>Open your chat and tap the attachment icon (the paperclip or plus button).</li>
  <li>Select <strong>'Document'</strong>.</li>
  <li>Choose 'Browse other docs' or browse your local file manager.</li>
  <li>Find the image file (usually in your Camera, Downloads, or screenshots folder) and send it.</li>
</ol>
<p>When sent as a document, WhatsApp treats the image as a binary file. It transfers the file raw without applying any image processing, ensuring the receiver gets the exact byte-for-byte replica with all pixels and metadata intact.</p>

<h4>Method 2: Use the 'HD' Toggle</h4>
<p>Recent updates to WhatsApp include an 'HD' button at the top of the photo preview screen before sending. Tapping this allows you to choose 'HD Quality' (often up to 3000px wide) rather than 'Standard Quality'. While this still applies some compression, it is far less aggressive than the default settings, preserving much of the original detail.</p>

<h4>Method 3: Pre-optimize Dimensions</h4>
<p>If you are sharing promotional banners or designs, pre-scale the canvas to matching viewport limits (such as 800x800px) using our resizer tool. By exporting the image near the app's target display dimensions, you prevent the native downscaling algorithm from running, keeping your text and icons sharp.</p>
        """
    },
    "best-image-format-for-websites": {
        "title": "What is the Best Image Format for Websites in 2026?",
        "summary": "Stop using raw PNGs for website banners. We analyze the best image formats to keep your page speeds high and bounce rates low.",
        "reading_time": "5 min read",
        "date": "July 10, 2026",
        "category": "SEO Guides",
        "content": """
<h2>Selecting the Right Web Image Formats</h2>
<p>Slow page load times hurt conversions. If a website takes more than 3 seconds to load, about 40% of visitors drop off immediately. Since images account for more than 60% of an average page's weight, picking the right format is the easiest way to speed up your site and lower bounce rates. In this guide, we break down the best image formats to use for different website elements in 2026.</p>

<h3>Detailed Analysis of Formats by Use Case</h3>
<p>Using a single image format for everything on a website leads to poor performance. Instead, assign formats based on the layout context:</p>

<h4>1. Icons, Badges, and Text Graphics: Use SVG</h4>
<p>Scalable Vector Graphics (SVG) are code-based XML templates. They contain coordinate paths rather than pixel grids. Because they are vectors, you can scale them infinitely without losing quality. A detailed company logo saved as an SVG usually weighs under 5KB, whereas the same logo in PNG format might weigh 80KB. Always use SVGs for UI graphics, navigation icons, and brand badges.</p>

<h4>2. Photographs, Product Grids, and Blog Headers: Use WebP or AVIF</h4>
<p>For photographic images, next-generation raster formats like WebP or AVIF are the best choice. They use advanced compression algorithms to keep file sizes small while maintaining rich details. Converting your hero images from JPEG to WebP or AVIF can reduce your image payload by up to 50%, improving your page loading times.</p>

<h4>3. SaaS Dashboards and Screenshots: Use PNG</h4>
<p>If you need to show screenshots of a software dashboard or a chart containing fine text, PNG is still the most reliable option. Because PNG is lossless, it keeps text lines and UI border pixels sharp. JPG compression often creates blurry artifacts around text elements, making screenshots hard to read.</p>

<h3>Understanding Web Performance Metrics (Core Web Vitals)</h3>
<p>Google evaluates website quality using Core Web Vitals, focusing on two key metrics related to images:</p>
<ul>
  <li><strong>Largest Contentful Paint (LCP):</strong> Measures how long it takes for the main content block (often a hero image) to become visible. Using AVIF or WebP for header banners directly improves LCP.</li>
  <li><strong>Cumulative Layout Shift (CLS):</strong> Measures page stability as elements load. Always define <code>width</code> and <code>height</code> attributes on your HTML <code>&lt;img&gt;</code> tags to reserve layout space, preventing layout shifts when images load.</li>
</ul>

<h3>Web Performance Checklist</h3>
<ol>
  <li><strong>Convert to Modern Formats:</strong> Use WebP or AVIF for photos and banners.</li>
  <li><strong>Resize to Viewport Targets:</strong> Never serve a 3000px image if the display container is only 600px wide. Downsize the pixel dimensions before uploading.</li>
  <li><strong>Set Explicit Dimensions:</strong> Define width and height on your image tags to prevent layout shifts.</li>
  <li><strong>Compress File Sizes:</strong> Keep landing page images under 150KB to ensure fast loading times on mobile networks.</li>
</ol>
        """
    },
    "how-to-reduce-image-size-without-losing-quality": {
        "title": "How to Reduce Image Size Without Losing Quality",
        "summary": "A guide to smart lossy compression. Learn how to shrink file sizes to specific targets while maintaining perfect visual quality.",
        "reading_time": "5 min read",
        "date": "July 10, 2026",
        "category": "Compression",
        "content": """
<h2>Fidelity Optimization: Shrink Images Losslessly</h2>
<p>Reducing file size doesn't mean you have to compromise on visual clarity. Through smart optimization techniques, you can shrink image bytes dramatically while keeping the output looking crisp to the human eye. In this masterclass, we explain the mechanics of lossy and lossless compression, how quantizers work, and how to optimize images to specific target file sizes.</p>

<h3>The Concept: Lossless vs. Lossy Compression</h3>
<p>To reduce file size, you need to understand the difference between the two main types of compression:</p>
<ul>
  <li><strong>Lossless Compression:</strong> This method reorganizes the file data without removing any details. It functions like a ZIP archive, compressing patterns of duplicate pixels. While it keeps the image pixel-perfect, the file size reduction is limited (often only 10-25%).</li>
  <li><strong>Lossy Compression:</strong> This method discards color detail and pixel data that the human eye cannot easily perceive. Human eyes are highly sensitive to brightness details but less sensitive to minor shifts in color hue. Lossy compression exploits this limitation to shrink file sizes by up to 80% while keeping the image virtually identical to the original.</li>
</ul>

<h3>How to Compress Smartly</h3>
<p>To achieve high compression ratios without making your images look blurry, follow these three steps:</p>

<h4>1. Target Perceptual Quality Thresholds</h4>
<p>Most digital cameras save photos at 100% quality, which embeds duplicate color data. Compressing the quality level to 80% or 82% reduces file size by up to 70% while keeping the details visually indistinguishable from the original. Only go below 70% quality if file size constraints are strict, as compression artifacts will start to appear.</p>

<h4>2. Strip EXIF Metadata</h4>
<p>Raw photos contain embedded metadata tags (EXIF data) that store camera settings, exposure settings, GPS coordinates, capture dates, and color profiles. While useful for photographers, this metadata is unnecessary for web display and can add up to 50KB of weight. Stripping this metadata during compression reduces file size without affecting the image pixels at all.</p>

<h4>3. Scale Pixel Dimensions First</h4>
<p>A common mistake is uploading a 4000x3000 pixel image and scaling it down in HTML using CSS. The browser still has to download the full-sized file, slowing down the page load. Downscale the image dimensions to match your display container (such as 800x600px for a card thumbnail) before compressing. Resizing the pixel grid first yields the largest file size savings.</p>

<h3>Step-by-Step Optimization Workflow</h3>
<ol>
  <li>Upload your original image into our optimizer tool.</li>
  <li>If the image is destined for a specific layout container, enter the exact target width and height in the Resizer tab.</li>
  <li>Set the target file size slider in the Compressor tab (for example, to 100KB or 200KB).</li>
  <li>Run the process. Our engine will dynamically downscale the image, strip unnecessary metadata, and run iterative compression sweeps to meet your target file size while maintaining visual quality.</li>
</ol>
        """
    },
    "mp4-vs-webm": {
        "title": "MP4 vs WebM: Which Video Format is Best for Websites?",
        "summary": "When embedding video content directly onto your website, choosing the correct video format is critical. Serving raw or poorly encoded videos slows down page loading, consumes massive amounts of server bandwidth, and leads to a bad user experience. The two primary video formats used on the modern web are MP4 and WebM. In this guide, we analyze their technical structures, compression performance, browser compatibility, and deployment strategies.",
        "reading_time": "5 min read",
        "date": "July 10, 2026",
        "category": "Video Guides",
        "content": """
<h2>Understanding MP4 and WebM Codecs</h2>
<p>When embedding video content directly onto your website, choosing the correct video format is critical. Serving raw or poorly encoded videos slows down page loading, consumes massive amounts of server bandwidth, and leads to a bad user experience. The two primary video formats used on the modern web are MP4 and WebM. In this guide, we analyze their technical structures, compression performance, browser compatibility, and deployment strategies.</p>

<h3>What is MP4 (MPEG-4 Part 14)?</h3>
<p>MP4 is a digital multimedia container format most commonly used to store video and audio. In web design, an MP4 container typically wraps video encoded with the H.264 video codec and audio encoded with the AAC audio codec. MP4 with H.264 is the most universally compatible video format in existence. It plays natively on virtually every web browser, operating system, and mobile device, including older legacy platforms.</p>
<p>Because H.264 is widely supported, many devices feature hardware-accelerated decoding for it. This means the device's processor has dedicated chips to run the video playback, which reduces battery consumption and keeps playback smooth, even on low-end smartphones. However, H.264 compression is less efficient than modern codecs, resulting in larger file sizes for the same quality level.</p>
<ul>
  <li><strong>Best for:</strong> Maximum cross-device compatibility, emails, and legacy browser support.</li>
  <li><strong>Pros:</strong> Universal native playback, hardware acceleration, and stable color rendering.</li>
  <li><strong>Cons:</strong> Larger file sizes compared to modern codecs like VP9 or AV1.</li>
</ul>

<h3>What is WebM (Google Web Media)?</h3>
<p>WebM is a media file format introduced by Google in 2010. It is designed specifically for use in HTML5 web pages. A WebM container typically wraps video compressed with the VP8 or VP9 video codecs, and audio compressed with the Vorbis or Opus audio codecs. WebM is fully royalty-free and open-source.</p>
<p>WebM using the VP9 codec offers much better compression efficiency than MP4 with H.264. VP9 compression reduces video file sizes by 30% to 50% compared to H.264 while maintaining identical visual quality. This reduction directly speeds up page loading times and saves server bandwidth costs. However, legacy browsers and older iOS devices (older than iOS 14) do not support WebM natively, and hardware-accelerated decoding is less common for VP9 on older mobile chips.</p>
<ul>
  <li><strong>Best for:</strong> Web embeds, autoplay background videos, and high-performance layouts.</li>
  <li><strong>Pros:</strong> Excellent compression ratios, small file sizes, and open-source.</li>
  <li><strong>Cons:</strong> Lacks hardware acceleration on some older devices, leading to slightly higher CPU use.</li>
  <li><strong>Browser Support:</strong> Fully supported on 96%+ of modern browsers, including Safari on iOS 15+.</li>
</ul>

<h3>Technical Comparison: Widescreen Video Embeds</h3>
<p>If you embed a 10-second autoplay hero background video on your homepage as an MP4, it might weigh 12MB. If you convert that video to WebM using the VP9 codec and apply optimal compression, the file size can drop to 4.5MB. For a landing page, this 60%+ drop in file size is critical. It helps you pass Google's Largest Contentful Paint (LCP) test and lowers mobile data usage for your visitors.</p>

<h3>How to Deploy Video on the Web</h3>
<p>To get the best of both formats—small file sizes and universal compatibility—always use the HTML5 <code>&lt;video&gt;</code> tag with multiple source files. The browser will automatically evaluate the list in order and load the first format it supports:</p>
<pre><code>&lt;video autoplay loop muted playsinline width="1200" height="675"&gt;
  &lt;source src="background.webm" type="video/webm"&gt;
  &lt;source src="background.mp4" type="video/mp4"&gt;
  Your browser does not support the video tag.
&lt;/video&gt;</code></pre>
<p>In this structure, modern browsers will load the lightweight WebM file first, while older Apple devices or legacy browsers will fall back to the universally supported MP4 file. Note that attributes like <code>muted</code> and <code>playsinline</code> are required for background videos to autoplay on mobile platforms.</p>
        """
    },
    "compress-video-for-web": {
        "title": "How to Compress Video Files for Web Without Quality Loss",
        "summary": "High-quality video content is highly engaging, but it is also the heaviest resource you can add to a website. A single raw video file can easily exceed 100MB, which slows down page speeds, increases user bounce rates, and consumes server bandwidth. To keep your website fast, you must compress your video files. In this guide, we explain the mechanics of video compression and outline how to shrink your video files while maintaining excellent visual quality.",
        "reading_time": "5 min read",
        "date": "July 10, 2026",
        "category": "Video Guides",
        "content": """
<h2>Fidelity Optimization: Compress Web Videos</h2>
<p>High-quality video content is highly engaging, but it is also the heaviest resource you can add to a website. A single raw video file can easily exceed 100MB, which slows down page speeds, increases user bounce rates, and consumes server bandwidth. To keep your website fast, you must compress your video files. In this guide, we explain the mechanics of video compression and outline how to shrink your video files while maintaining excellent visual quality.</p>

<h3>The Concept: Video Bitrates and Codecs</h3>
<p>Video files are heavy because they are composed of a sequence of static images (frames) played back rapidly, usually at 24, 30, or 60 frames per second. Video compression works by removing redundant visual data within each frame (spatial compression) and across consecutive frames (temporal compression). Temporal compression is particularly powerful: instead of saving every pixel of every frame, the codec only saves the pixels that change from one frame to the next.</p>
<p>The main setting that determines both video quality and file size is the **bitrate** (the amount of data processed per second, measured in Mbps or Kbps). A high bitrate yields a clear picture but a large file size. The goal of web optimization is to find the lowest possible bitrate that still looks crisp on standard viewports.</p>

<h3>Three Golden Rules of Web Video Compression</h3>
<p>To shrink your videos without introducing noticeable pixelation, apply these optimization techniques:</p>

<h4>1. Use the Right Video Codec (H.264 or VP9)</h4>
<p>The codec you choose has a major impact on compression efficiency. For general compatibility, compress your videos using the H.264 codec inside an MP4 container. For maximum compression, convert your files to WebM using the VP9 codec. VP9 offers up to 50% better compression than H.264, allowing you to maintain high visual quality at much lower bitrates.</p>

<h4>2. Lock Resolutions and Frame Rates</h4>
<p>Never upload raw 4K videos to a website. Most users view web content on screens that display at 1080p (1920x1080) or smaller. Downscale your video resolution to 1080p or 720p before compressing. Additionally, check the frame rate: unless you are displaying fast-moving sports or gaming content, reduce the frame rate from 60fps to a standard 24fps or 30fps. This change instantly cuts the data payload in half.</p>

<h4>3. Strip Unnecessary Audio Tracks</h4>
<p>If your video is designed to autoplay as a silent background banner or header, remove the audio track entirely during compression. Keeping an empty or silent audio track in the container still requires data processing and adds unnecessary bytes to the file. Stripping the audio stream can save up to 10% of the overall file size and ensures mobile browsers autoplay the video reliably.</p>

<h3>Step-by-Step Compression Workflow</h3>
<ol>
  <li>Upload your video file (MP4, WebM, or MOV) into our online compressor tool.</li>
  <li>Enter the target resolution (such as 1200px wide for banners) in the Resize tab.</li>
  <li>Set your target quality compression level or target size (such as 5MB) in the Compressor tab.</li>
  <li>Run the process. Our backend engine uses optimized ffmpeg profiles to adjust bitrate limits, strip audio streams, and re-encode the file to keep it under your target size while maintaining visual quality.</li>
</ol>
        """
    },
    "how-to-watermark-videos": {
        "title": "How to Add a Logo Watermark to Video Content Online",
        "summary": "With the rapid growth of short-form video feeds on TikTok, Instagram Reels, and YouTube Shorts, content creators face a common problem: video theft. It is incredibly easy for users to download your video, re-upload it to their own channel, and claim credit for your work. To prevent unauthorized use and build brand recognition, you should overlay a logo watermark onto your video content. In this guide, we explain the styling best practices and technical steps to watermark your videos online.",
        "reading_time": "5 min read",
        "date": "July 10, 2026",
        "category": "Video Guides",
        "content": """
<h2>Protecting Your Video Assets with Watermarks</h2>
<p>With the rapid growth of short-form video feeds on TikTok, Instagram Reels, and YouTube Shorts, content creators face a common problem: video theft. It is incredibly easy for users to download your video, re-upload it to their own channel, and claim credit for your work. To prevent unauthorized use and build brand recognition, you should overlay a logo watermark onto your video content. In this guide, we explain the styling best practices and technical steps to watermark your videos online.</p>

<h3>Why Add a Watermark to Your Videos?</h3>
<p>A watermark is a subtle, transparent logo overlay placed in a corner of your video. It serves two main purposes:</p>
<ol>
  <li><strong>Intellectual Property Protection:</strong> A permanent watermark makes it difficult for copycat channels to scrape your content. If they try to crop the watermark out, they will ruin the video's composition, making it less appealing to viewers.</li>
  <li><strong>Brand Recognition:</strong> When your video goes viral, millions of viewers will see your logo. Even if other accounts share it, your brand identity remains visible, driving organic traffic back to your official profile.</li>
</ol>

<h3>Best Practices for Video Watermark Design</h3>
<p>A poorly designed watermark can distract viewers and ruin the look of your video. To keep your branding professional, follow these guidelines:</p>
<ul>
  <li><strong>Use a Transparent PNG Logo:</strong> Never use a logo with a solid white or black background box. Export your logo as a PNG with a transparent alpha channel so only the icon or text overlays the video frames.</li>
  <li><strong>Adjust Opacity (Transparency):</strong> Keep the logo semi-transparent. Setting the watermark's opacity to around 30% to 50% ensures it is clearly visible without blocking the underlying video action.</li>
  <li><strong>Keep the Size Subtle:</strong> The watermark should not occupy more than 8% to 10% of the overall video canvas. It should be small enough to stay out of the way but large enough to remain readable.</li>
  <li><strong>Position Strategically:</strong> Place your watermark in one of the corners (such as the bottom-right or top-left). Avoid placing it near the edges where social media app interfaces (like TikTok's like button or video description) might overlay and cover it.</li>
</ul>

<h3>How to Watermark Videos in Bulk Online</h3>
<p>Manually editing every video file in desktop software to add a watermark takes a lot of time. Our online tool allows you to watermark videos in bulk directly inside your browser: </p>
<ol>
  <li>Upload your videos (MP4, WebM, or MOV) into the drag-and-drop workspace.</li>
  <li>Under the Watermark tab, upload your transparent PNG logo.</li>
  <li>Select your placement mode (such as Top Right, Bottom Right, or Smart Placement).</li>
  <li>Click Process Files. Our processing engine will overlay the logo, adjust transparency, and compile the video frames securely.</li>
  <li>Download your watermarked video files individually or as a single ZIP archive.</li>
</ol>
        """
    }
}


def get_all_paths() -> list[str]:
    """Generate all sitemap-friendly paths dynamically."""
    paths = [
        # core tools
        "resize-image",
        "compress-image",
        "convert-image",
        "watermark-image",
        # video core tools
        "resize-video",
        "compress-video",
        "convert-video",
        "watermark-video",
    ]
    
    # format conversions (selected combinations)
    for fmt_from in IMAGE_FORMATS + VIDEO_FORMATS:
        for fmt_to in ["jpg", "png", "webp", "gif", "mp4", "webm"]:
            if fmt_from != fmt_to:
                # avoid invalid video-to-image or image-to-video if not supported
                is_from_video = fmt_from in VIDEO_FORMATS and fmt_from != "gif"
                is_to_video = fmt_to in {"mp4", "webm"}
                if is_from_video and not is_to_video:
                    continue
                if is_to_video and not is_from_video and fmt_from not in {"png", "jpg", "jpeg", "webp"}:
                    continue
                paths.append(f"{fmt_from}-to-{fmt_to}")
                
    # dimensions
    for preset in POPULAR_DIMENSIONS:
        paths.append(f"resize-image-to-{preset['width']}x{preset['height']}")
        
    # platforms
    for platform in PLATFORM_PRESETS.keys():
        paths.append(f"resize-image-for-{platform}")
        
    # compression limits
    for size in FILE_SIZE_PRESETS:
        paths.append(f"compress-image-to-{size}kb")
    paths.append("compress-image-under-1mb")
    
    # use cases
    for uc in USE_CASES.keys():
        paths.append(f"{uc}-resizer")
        paths.append(f"image-for-{uc}")
        
    # blog posts
    for slug in BLOG_ARTICLES.keys():
        paths.append(f"blog/{slug}")
        
    # static paths
    paths.extend(["about", "contact", "privacy", "terms"])
    
    return paths


def resolve_seo_data(path: str) -> dict | None:
    """Analyze path and return custom SEO metadata and configuration presets."""
    path = path.strip("/").lower()
    
    # default variables
    data = {
        "canonical": f"/{path}",
        "active_tab": "compress",
        "h1": "",
        "title": "",
        "meta_description": "",
        "intro_copy": "",
        "benefits": [],
        "how_it_works": [],
        "faqs": [],
        "preset_data": {},
        "related_links": [],
        "schema_markup": {},
        "is_video": False,
        "ad_config": {
            "client_id": ADS_CLIENT_ID,
            "top_slot": "top-leaderboard-ad",
            "sidebar_left_slot": "left-sidebar-ad",
            "sidebar_right_slot": "right-sidebar-ad",
            "mid_slot": "mid-content-ad",
            "bottom_slot": "bottom-leaderboard-ad"
        }
    }
    
    # Case 1: Core pages
    if path == "":
        data["title"] = "globeoptimiser.com — Premium Bulk Image Resizer & Compressor"
        data["meta_description"] = "Resize dimensions, compress to target limits in KB, and watermark branding onto your creative banners. Direct, fast, and entirely in your browser."
        data["h1"] = "The Easiest Way to <mark>Optimise</mark> Banners & Images"
        data["intro_copy"] = "Bulk resize dimensions, compress files to target limits, and stamp brand logos onto your creative banners. Direct, fast, and entirely inside your browser."
        data["active_tab"] = "compress"
        data["benefits"] = [
            {"title": "Online Image Optimizer", "desc": "Accelerate your site speed with our leading optimizer. Improve page load speeds and search rankings."},
            {"title": "Free Online Image Compressor", "desc": "Reduce image sizes to a specific KB limit or scale your creatives easily with our high-fidelity engine."},
            {"title": "Bulk Image Resizer", "desc": "Batch process dozens of banner formats in a single click, saving hours of manual exporting work."},
            {"title": "Logo Watermark Tool", "desc": "Protect your brand assets by automatically stamping custom logo graphics on bulk images."}
        ]
        data["how_it_works"] = [
            "Upload the banner files you want to optimize.",
            "Choose your tool tab: Compress, Resize, or Stamp Logo.",
            "Configure limits or dimensions, then click Process Files."
        ]
        data["faqs"] = [
            {"q": "Is my data safe on globeoptimiser?", "a": "Yes! All processing runs securely in our high-performance engine. Your files are never stored permanently."},
            {"q": "Can I process animations?", "a": "Yes, our engine supports compressing and converting animated GIF files, helping you optimize them for web page headers."},
            {"q": "Is there a bulk file limit?", "a": "You can process multiple files simultaneously up to a total batch size of 50MB."}
        ]
        return data
        
    elif path == "resize-image":
        data["title"] = "Free Bulk Image Resizer Online — Resize Banners & Images"
        data["meta_description"] = "Resize images to custom width and height in bulk. Fit, crop, blur margins, and change dimensions of multiple files instantly."
        data["h1"] = "Free Online <mark>Bulk Image Resizer</mark>"
        data["intro_copy"] = "Adjust pixel dimensions, expand background canvases with dominant fills, and resize multi-format image banners for marketing campaigns in seconds."
        data["active_tab"] = "resize"
        data["benefits"] = [
            {"title": "Precision Scaling", "desc": "Enter exact pixel width and height boundaries to scale creatives perfectly."},
            {"title": "Margin Filler Modes", "desc": "Fill empty backgrounds using dominant color matching or blur effects."},
            {"title": "Fast Processing", "desc": "Batch export scaled assets instantly to avoid manual adjustments."}
        ]
        data["how_it_works"] = [
            "Upload your banner assets into the resizer box.",
            "Enter target Width and Height in pixels.",
            "Select a background adapt mode and click Process Files."
        ]
        data["faqs"] = [
            {"q": "What is Aspect Ratio Locking?", "a": "Locking the ratio ensures your image does not stretch. When you edit width, height scales automatically to prevent distortion."},
            {"q": "What background adapt mode should I use?", "a": "Use 'Fit & Expand (Dominant Color)' for clean graphic banners, or 'Blur Expand' for photographic imagery."}
        ]
        return data
        
    elif path == "compress-image":
        data["title"] = "Online Image Compressor — Reduce Image Size in KB"
        data["meta_description"] = "Reduce image file size to a specific KB target limit without losing quality. Bulk compress JPG, PNG, and WebP files online."
        data["h1"] = "Free Online <mark>Image Compressor</mark>"
        data["intro_copy"] = "Target specific file sizes in KB. Our intelligent lossy compression shrinks image weights while retaining stunning visual quality."
        data["active_tab"] = "compress"
        data["benefits"] = [
            {"title": "Target KB Compression", "desc": "Set an exact target file size, and the engine adjusts parameters to hit the target."},
            {"title": "Lossless Fidelity Visuals", "desc": "Retains image clarity by targeting human vision thresholds."},
            {"title": "Core Web Vitals Boost", "desc": "Shrink heavy images to speed up pages, boosting user metrics."}
        ]
        data["how_it_works"] = [
            "Drag and drop your images into the upload container.",
            "Set the target file size slider to your preferred KB limit.",
            "Click Process Files to shrink files and download."
        ]
        data["faqs"] = [
            {"q": "How does target KB compression work?", "a": "Our engine runs iterative compression sweeps, modifying export quality parameters until the file hits your specified limit."},
            {"q": "Will my images look blurry?", "a": "No, the compression scales color densities that are invisible to human eyes, maintaining crisp details."}
        ]
        return data
        
    elif path == "convert-image":
        data["title"] = "Online Image Converter — Convert Image Format Free"
        data["meta_description"] = "Convert image formats in bulk. Fast file conversion between JPG, PNG, WEBP, BMP, GIF, AVIF, and HEIC."
        data["h1"] = "Free Online <mark>Image Converter</mark>"
        data["intro_copy"] = "Convert formats instantly. Seamlessly transform images to next-generation formats like WEBP or PNG."
        data["active_tab"] = "convert"
        data["benefits"] = [
            {"title": "Next-Gen Format Exports", "desc": "Convert standard assets to modern WebP files to save up to 40% bandwidth."},
            {"title": "Transparency Support", "desc": "Convert vectors or transparencies cleanly to PNG or WEBP formats."},
            {"title": "Animated GIF Support", "desc": "Easily compress heavy animated graphics to optimize page rendering times."}
        ]
        data["how_it_works"] = [
            "Upload the files you need to convert.",
            "Select the Convert tab and choose your target format.",
            "Process the files to download converted versions."
        ]
        data["faqs"] = [
            {"q": "Can I convert HEIC to JPG?", "a": "Yes! Upload HEIC images shot on Apple devices and export them as highly compatible JPG or WebP files."},
            {"q": "Which format is best for web performance?", "a": "WebP offers the best overall performance, supporting animations, transparency, and high compression rates."}
        ]
        return data
        
    elif path == "watermark-image":
        data["title"] = "Free Logo Watermark Tool — Add Logo to Image Online"
        data["meta_description"] = "Stamp custom logo graphics onto bulk images. Protect branding assets and add watermarks with customizable placements."
        data["h1"] = "Free Online <mark>Logo Watermark Tool</mark>"
        data["intro_copy"] = "Watermark banner uploads. Automatically place and stamp transparency-enabled logos onto folders of banners in one click."
        data["active_tab"] = "stamp"
        data["benefits"] = [
            {"title": "Branding Protection", "desc": "Easily overlay logo branding onto banners to prevent image theft."},
            {"title": "Smart Logo Positioning", "desc": "Use intelligent coordinates to automatically place logos in the least intrusive spot."},
            {"title": "Bulk Stamping", "desc": "Process unlimited banners simultaneously with custom logo templates."}
        ]
        data["how_it_works"] = [
            "Upload your banner photos and upload your logo branding graphic.",
            "Select logo placement mode (Smart, Top Left, or Top Right).",
            "Process the files to merge the images and download."
        ]
        data["faqs"] = [
            {"q": "What format should my logo be?", "a": "We recommend uploading a transparent PNG logo to ensure it overlays cleanly onto your background banners."},
            {"q": "What is Smart Placement?", "a": "Smart Placement evaluates the contrast and details of the background banner to place the logo where it is visible without blocking key subjects."}
        ]
        return data

    elif path == "resize-video":
        data["is_video"] = True
        data["title"] = "Free Bulk Video Resizer Online — Resize MP4 & WebM Dimensions"
        data["meta_description"] = "Resize video resolution and aspect ratios in bulk. Change video dimensions, scale pixel width and height online for social media formats."
        data["h1"] = "Free Online <mark>Bulk Video Resizer</mark>"
        data["intro_copy"] = "Quickly adjust video dimensions and aspect ratios in bulk. Scale your MP4 and WebM videos for YouTube, Instagram, or website feeds."
        data["active_tab"] = "resize"
        data["benefits"] = [
            {"title": "Precision Scaling", "desc": "Enter exact pixel values to resize your video files for targeted playbacks."},
            {"title": "Aspect Ratio Presets", "desc": "Lock proportions or adapt videos to standard vertical and widescreen formats."},
            {"title": "Optimized Web Output", "desc": "Reduces overall bandwidth consumption by scaling down frame dimensions."}
        ]
        data["how_it_works"] = [
            "Upload your video files (MP4, WebM, MOV, etc.).",
            "Specify the target Width and Height dimensions in pixels.",
            "Run processing to scale and download your formatted videos."
        ]
        data["faqs"] = [
            {"q": "Does resizing videos reduce their quality?", "a": "Only if you upscale a low-resolution video to a much larger canvas. Scaling down preserves clarity while shrinking the file size."},
            {"q": "Which video dimensions should I use for social media?", "a": "Use 1080x1920 for vertical videos (TikTok, Instagram Reels) and 1920x1080 for standard widescreen video players."}
        ]
        return data

    elif path == "compress-video":
        data["is_video"] = True
        data["title"] = "Online Video Compressor — Reduce Video File Size Free"
        data["meta_description"] = "Reduce video file size online in bulk. Compress MP4, WebM, and MOV videos to make them smaller without losing visual quality."
        data["h1"] = "Free Online <mark>Video Compressor</mark>"
        data["intro_copy"] = "Reduce video file size quickly. Our high-performance compressor removes redundant color details and optimizes encoding bits to shrink video weights."
        data["active_tab"] = "compress"
        data["benefits"] = [
            {"title": "Target Size Reduction", "desc": "Easily compress heavy video files to meet strict portal or email limits."},
            {"title": "Visual Quality Conservation", "desc": "Maintains crisp frame details using advanced quantization logic."},
            {"title": "Fast Encoding", "desc": "Optimize batches of video files in seconds directly inside your workspace."}
        ]
        data["how_it_works"] = [
            "Drag and drop your video files into the upload box.",
            "Set the compression level to control target size.",
            "Click Process Files to shrink and download optimized videos."
        ]
        data["faqs"] = [
            {"q": "Is video compression lossy?", "a": "Yes, but our compressor uses advanced encoding profiles that prioritize human vision thresholds, keeping details looking sharp."},
            {"q": "What video format compresses best?", "a": "WebM and MP4 formats provide the best compression-to-quality ratios for modern web environments."}
        ]
        return data

    elif path == "convert-video":
        data["is_video"] = True
        data["title"] = "Online Video Converter — Convert Video Formats Free"
        data["meta_description"] = "Convert video formats in bulk. Fast online video conversion between MP4, WebM, and animated GIF formats."
        data["h1"] = "Free Online <mark>Video Converter</mark>"
        data["intro_copy"] = "Convert video formats instantly. Seamlessly transform video clips between MP4, WebM, and animated GIFs in one click."
        data["active_tab"] = "convert"
        data["benefits"] = [
            {"title": "Cross-Format Compiles", "desc": "Convert legacy video clips to modern web-friendly formats."},
            {"title": "Video to GIF exports", "desc": "Easily turn short video sequences into lightweight animated graphic headers."},
            {"title": "Universal Playback", "desc": "Ensure your video files load and play on all devices and platforms."}
        ]
        data["how_it_works"] = [
            "Upload the videos you need to convert.",
            "Select your target video format (MP4, WebM, or GIF).",
            "Click Process Files to compile and save your files."
        ]
        data["faqs"] = [
            {"q": "Why should I convert to WebM?", "a": "WebM is optimized for the web, offering much smaller file sizes than MP4 and native HTML5 playback support."},
            {"q": "How do I turn a video into a GIF?", "a": "Upload your MP4 or WebM video file, select GIF as the target output format, and click Process Files."}
        ]
        return data

    elif path == "watermark-video":
        data["is_video"] = True
        data["title"] = "Free Video Watermark Tool — Add Logo to Video Online"
        data["meta_description"] = "Overlay custom logo graphics onto bulk videos. Protect your video branding assets with customizable watermark placements."
        data["h1"] = "Free Online <mark>Video Watermark Tool</mark>"
        data["intro_copy"] = "Protect your video creations. Automatically overlay transparent branding logos onto folders of videos in one click."
        data["active_tab"] = "stamp"
        data["benefits"] = [
            {"title": "Branding Defense", "desc": "Secure your video content from theft by stamping your official brand logo on top."},
            {"title": "Custom Placements", "desc": "Choose exactly where the watermark logo should overlay on the video layout."},
            {"title": "Batch Stamping", "desc": "Watermark multiple videos simultaneously with consistent templates."}
        ]
        data["how_it_works"] = [
            "Upload your video files and upload your logo branding graphic.",
            "Choose the placement position (Smart, Top Left, Bottom Right, etc.).",
            "Process files to merge the watermark and download."
        ]
        data["faqs"] = [
            {"q": "What logo format should I use?", "a": "A transparent PNG logo is recommended to ensure it blends seamlessly on top of your video background."},
            {"q": "Can I watermark multiple videos at once?", "a": "Yes, our batch engine stamps your uploaded logo template across the entire queue of videos simultaneously."}
        ]
        return data
        
    # Case 2: Programmatic Conversion Pages: {from}-to-{to}
    match_conv = re.match(r"^([a-z0-9]+)-to-([a-z0-9]+)$", path)
    if match_conv:
        fmt_from = match_conv.group(1).upper()
        fmt_to = match_conv.group(2).upper()
        
        is_vid = fmt_from.lower() in {"mp4", "webm", "mov", "avi"} or fmt_to.lower() in {"mp4", "webm"}
        if is_vid:
            data["is_video"] = True
            data["title"] = f"Convert {fmt_from} to {fmt_to} Online — Free Bulk Video Converter"
            data["meta_description"] = f"Convert {fmt_from} videos to {fmt_to} format in bulk. Safe, ultra-fast online conversion with maximum resolution and quality conservation."
            data["h1"] = f"Convert <mark>{fmt_from} to {fmt_to}</mark> Online"
            data["intro_copy"] = f"Transform your {fmt_from} video files into {fmt_to} format instantly. Select your files below to perform batch conversion securely inside your browser."
            data["active_tab"] = "convert"
            data["preset_data"] = {"target_format": fmt_to.lower()}
            data["benefits"] = [
                {"title": "Instant Conversions", "desc": f"Directly compile {fmt_from} to {fmt_to} without waiting for slow processing queues."},
                {"title": "Maximum Video Quality", "desc": "Our converting algorithm preserves frames and bitrate details perfectly."},
                {"title": "Bulk Upload Support", "desc": "Convert entire folder files at once, saving hours of manual encoding."}
            ]
            data["how_it_works"] = [
                f"Select or drop your {fmt_from} files in the workspace.",
                f"Open the Convert tab (configured automatically to export {fmt_to}).",
                "Click Process Files to convert and download."
            ]
            data["faqs"] = [
                {"q": f"Why should I convert {fmt_from} to {fmt_to}?", "a": f"Converting to {fmt_to} can improve compatibility with video players, reduce video files sizes, or help you upload to web platforms that block {fmt_from} formats."},
                {"q": "Is the conversion lossless?", "a": "Video conversions use high-bitrate encoding presets to ensure visual changes are indistinguishable from the original video source."}
            ]
        else:
            data["title"] = f"Convert {fmt_from} to {fmt_to} Online — Free Bulk Converter"
            data["meta_description"] = f"Convert {fmt_from} images to {fmt_to} format in bulk. Safe, ultra-fast online conversion with maximum resolution and quality conservation."
            data["h1"] = f"Convert <mark>{fmt_from} to {fmt_to}</mark> Online"
            data["intro_copy"] = f"Transform your {fmt_from} files into {fmt_to} format instantly. Select your files below to perform batch conversion securely inside your browser."
            data["active_tab"] = "convert"
            data["preset_data"] = {"target_format": fmt_to.lower()}
            data["benefits"] = [
                {"title": "Instant Conversions", "desc": f"Directly compile {fmt_from} to {fmt_to} without waiting for slow email delivery."},
                {"title": "Maximum Image Quality", "desc": "Our converting algorithm preserves colors and pixel details perfectly."},
                {"title": "Bulk Upload Support", "desc": "Convert entire folder files at once, saving hours of manual conversion."}
            ]
            data["how_it_works"] = [
                f"Select or drop your {fmt_from} files in the workspace.",
                f"Open the Convert tab (configured automatically to export {fmt_to}).",
                "Click Process Files to convert and download."
            ]
            data["faqs"] = [
                {"q": f"Why should I convert {fmt_from} to {fmt_to}?", "a": f"Converting to {fmt_to} can improve web compatibility, reduce image file sizes, or help you upload images to portals that block {fmt_from} extensions."},
                {"q": "Is the conversion lossless?", "a": f"If you convert to formats like PNG or WEBP, details remain pixel-perfect. JPEGs will use high-quality encoding (95%) to minimize loss."}
            ]
        return data
        
    # Case 3: Programmatic Resize Pages: resize-image-to-{width}x{height}
    match_res = re.match(r"^resize-image-to-([0-9]+)x([0-9]+)$", path)
    if match_res:
        w = int(match_res.group(1))
        h = int(match_res.group(2))
        
        data["title"] = f"Resize Image to {w}x{h} Pixels — Bulk Resize Tool"
        data["meta_description"] = f"Resize and crop your images to exactly {w}x{h} pixels online in bulk. Adjust banners, icons, and product photos to {w}x{h} resolution."
        data["h1"] = f"Resize Image to <mark>{w}x{h}</mark> Pixels"
        data["intro_copy"] = f"Instantly fit, crop, or blur borders of your images to standard {w}x{h} dimensions. Bulk process your creatives for marketing campaigns."
        data["active_tab"] = "resize"
        data["preset_data"] = {"width": w, "height": h}
        data["benefits"] = [
            {"title": "Exact Dimensional Lock", "desc": f"Force your output files to exactly {w}x{h} px without distortion."},
            {"title": "Canvas Fill Adaptations", "desc": "Use dominant color fill or gaussian blurs to pad margins beautifully."},
            {"title": "Optimized Output Weight", "desc": "Downscales image weights while rendering the layout, saving bandwidth."}
        ]
        data["how_it_works"] = [
            "Upload your banner graphics into the dropzone.",
            f"The width and height fields are pre-filled with {w}px by {h}px.",
            "Select your background border mode, then click Process Files."
        ]
        data["faqs"] = [
            {"q": f"Why is {w}x{h} resolution used?", "a": f"The {w}x{h} viewport is widely used for marketing banners, website sections, and social channels to achieve crisp layout rendering."},
            {"q": "Will my image stretch?", "a": "No, our background modes wrap your image to fit the container. The empty margins are filled with blur effects or solid colors."}
        ]
        return data

    # Case 4: Platform-Specific Pages: resize-image-for-{platform}
    match_plat = re.match(r"^resize-image-for-([a-z0-9]+)$", path)
    if match_plat:
        platform_key = match_plat.group(1)
        if platform_key in PLATFORM_PRESETS:
            preset = PLATFORM_PRESETS[platform_key]
            pname = preset["name"]
            
            data["title"] = f"Resize Image for {pname} Banners — Bulk Preset Tool"
            data["meta_description"] = f"Quickly resize and optimize your images for {pname}. Auto-fit covers, profile pictures, stories, and post dimensions for {pname} feeds."
            data["h1"] = f"Resize Image for <mark>{pname}</mark>"
            data["intro_copy"] = f"Keep your branding crisp on {pname}. {preset['description']} Select your files to scale and crop layouts using official {pname} size guidelines."
            data["active_tab"] = "resize"
            data["preset_data"] = {"platform": platform_key, "sizes": preset["sizes"]}
            data["benefits"] = [
                {"title": "Official Guidelines matching", "desc": f"All presets match official {pname} layout specifications."},
                {"title": "One-Click Resizing", "desc": "Toggle standard feeds, profiles, and cover styles instantly."},
                {"title": "Stunning Feed Quality", "desc": "Maintains crisp pixel ratios to survive native compression algorithms."}
            ]
            data["how_it_works"] = [
                "Select the files you need to prepare.",
                f"Choose the pre-configured dimension tags for {pname}.",
                "Process files to save formatted and compressed banners."
            ]
            data["faqs"] = [
                {"q": f"What are common mistakes on {pname}?", "a": preset["mistakes"]},
                {"q": f"What are {pname} image best practices?", "a": preset["best_practice"]}
            ]
            return data

    # Case 5: File Size Pages: compress-image-to-{size}kb or under-1mb
    match_size = re.match(r"^compress-image-to-([0-9]+)kb$", path)
    size_kb = None
    if match_size:
        size_kb = int(match_size.group(1))
    elif path == "compress-image-under-1mb":
        size_kb = 1000
        
    if size_kb is not None:
        size_label = f"{size_kb}KB" if size_kb < 1000 else "1MB"
        data["title"] = f"Compress Image to {size_label} — Reduce File Size Online"
        data["meta_description"] = f"Shrink image files to {size_label} or less online. Intelligent compression tool to reduce JPG and PNG sizes under {size_label} target limit."
        data["h1"] = f"Compress Image to <mark>{size_label}</mark>"
        data["intro_copy"] = f"Reduce file sizes to exactly {size_label} limit. Our processing sweep runs lossless adjustments to hit your target size constraint."
        data["active_tab"] = "compress"
        data["preset_data"] = {"target_size_kb": min(size_kb, 500) if size_kb < 1000 else 500}
        data["benefits"] = [
            {"title": "Strict Boundary Caps", "desc": f"Forces files to fall under {size_label} to pass portal limits."},
            {"title": "Optimized Upload Speed", "desc": "Lighter files load dramatically faster, lowering user bounce rates."},
            {"title": "Batch Quality Conservation", "desc": "Compresses folders of assets simultaneously while preserving details."}
        ]
        data["how_it_works"] = [
            "Upload the files you need to shrink.",
            f"The target file size slider will be automatically prefilled to {size_kb}KB.",
            "Run processing to export optimized assets immediately."
        ]
        data["faqs"] = [
            {"q": f"Why do I need my image to be under {size_label}?", "a": f"Many portals (such as government applications, job platforms, and email clients) enforce file limits like {size_label} to save database storage."},
            {"q": "What happens if the target is too small?", "a": "If your image is very large and the target is set extremely small, our engine uses the maximum compression threshold that preserves layout readability."}
        ]
        return data

    # Case 6: Use-Case Pages
    use_case_key = None
    if path.endswith("-resizer"):
        use_case_key = path.replace("-resizer", "")
    elif path.startswith("image-for-"):
        use_case_key = path.replace("image-for-", "")
        
    if use_case_key in USE_CASES:
        uc = USE_CASES[use_case_key]
        pname = uc["name"]
        w = uc["width"]
        h = uc["height"]
        
        data["title"] = f"Online {pname} Resizer — Format Photos for {pname}"
        data["meta_description"] = f"Scale and crop photos for your {pname} online. Auto-adjust dimensions to {w}x{h} px, compress file size, and download templates."
        data["h1"] = f"Online <mark>{pname}</mark> Resizer"
        data["intro_copy"] = f"Prepare your photos for {pname} uploads easily. {uc['advice']} Select your file below to resize and compress standard templates."
        data["active_tab"] = "resize"
        data["preset_data"] = {"width": w, "height": h}
        data["benefits"] = [
            {"title": "Exact Template Match", "desc": f"Resize photos directly to {w}x{h} pixels, the optimal size for {pname} uploads."},
            {"title": "Instant Compression", "desc": "Compiles and reduces file size parameters to ensure quick portal acceptance."},
            {"title": "No Registration Required", "desc": "Use our high-speed, free browser engine immediately without accounts."}
        ]
        data["how_it_works"] = [
            "Select your photo or headshot image.",
            f"The dimensions are locked to {w}x{h} pixels for {pname} format.",
            "Process the file and save the crop template."
        ]
        data["faqs"] = [
            {"q": f"What are requirements for {pname}?", "a": uc["advice"]},
            {"q": "How long does processing take?", "a": "Images process in less than a second, letting you download and submit your photos instantly."}
        ]
        return data

    # Case 7: Static Content Pages
    if path in ["about", "privacy", "terms", "contact"]:
        data["title"] = f"{path.capitalize()} Us — globeoptimiser.com"
        data["meta_description"] = f"Learn more about globeoptimiser.com. Review our {path} information, user guides, and contact details."
        return data

    return None


def get_blog_post(slug: str) -> dict | None:
    """Retrieve full blog post details by slug."""
    slug = slug.strip("/").lower()
    return BLOG_ARTICLES.get(slug)


def get_related_links(path: str) -> list[dict]:
    """Calculate internal links to prevent isolated pages and build solid structure."""
    path = path.strip("/").lower()
    links = []
    
    is_video = "video" in path or any(p in path for p in ["mp4", "webm", "gif"])
    
    if is_video:
        # Video related links
        if path != "resize-video":
            links.append({"url": "/resize-video", "title": "Video Resizer"})
        if path != "compress-video":
            links.append({"url": "/compress-video", "title": "Video Compressor"})
        if path != "convert-video":
            links.append({"url": "/convert-video", "title": "Video Converter"})
        if path != "watermark-video":
            links.append({"url": "/watermark-video", "title": "Video Watermark"})
            
        links.append({"url": "/blog/mp4-vs-webm", "title": "Guide: MP4 vs WebM"})
        links.append({"url": "/blog/compress-video-for-web", "title": "Guide: Video Compression"})
        links.append({"url": "/blog/how-to-watermark-videos", "title": "Guide: Video Watermarks"})
    else:
        # Image related links
        if path != "resize-image":
            links.append({"url": "/resize-image", "title": "Bulk Image Resizer"})
        if path != "compress-image":
            links.append({"url": "/compress-image", "title": "Image Compressor"})
        if path != "convert-image":
            links.append({"url": "/convert-image", "title": "Format Converter"})
        if path != "watermark-image":
            links.append({"url": "/watermark-image", "title": "Watermark Stamp"})
            
        links.append({"url": "/blog/jpg-vs-png", "title": "Guide: JPG vs PNG"})
        links.append({"url": "/blog/webp-vs-avif", "title": "Guide: WebP vs AVIF"})
        links.append({"url": "/blog/why-whatsapp-reduces-image-quality", "title": "Guide: WhatsApp Quality"})
        
    return links
