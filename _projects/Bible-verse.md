---
layout: page
title: Bible-verse
description: a web and commandline based tool to suggests Bible verses based on feeling
img: assets/img/273381354-876484a2-77f4-4bef-be3c-398888cc3e52.png
importance: 1
category: fun
---

Bibleverse is a commandline and web tool that helps you find the bible verses that speak the most to your circumstance.

Religious people and most especially christians find solace in the written word about their faith, the Bible. However, the Bible contains 66 books and many verses that talk about different things and circumstances. This tool is geared towards helping christians find relevant verses from the Bible that is directed towards their conditions

<div class="row">
    <div class="col-sm mt-3 mt-md-0">
        {% include figure.html path="assets/img/273381354-876484a2-77f4-4bef-be3c-398888cc3e52.png" title="example image" class="img-fluid rounded z-depth-1" %}
    </div>
</div>
<div class="caption">
    Command line interface of the Bibleverse tool asking for the user's name, how they are feeling and the result of the query
</div>
<div class="row">
    <div class="col-sm mt-3 mt-md-0">
        {% include figure.html path="assets/img/273381356-77014a88-d520-448c-95d3-f03f78860bd5.png" title="example image" class="img-fluid rounded z-depth-1" %}
    </div>

</div>
<div class="caption">
    Web interface of the Bibleverse tool asking for the user's name, how they are feeling and the result of the query
</div>

<!-- GETTING STARTED -->
## Getting Started

To get started and set up the project in your local environment, please download the packages listed in the requirements

### Installation

1. Create a virtual environment
    ```sh
    python -m venv .venv
    ```
2. Activate the virtual environment
    ```sh
    source .venv/bin/activate
    ```
3. Clone the repo
   ```sh
   git clone https://github.com/Ajalamarvellous/bibleverse.git
   ```
4. Install the necessary packages
   ```sh
   pip install requirements
   ```

   And you are ready to rumble


<!-- USAGE EXAMPLES -->
## Usage

To try out the software, you can use the commandline or through the web.

To use the commandline
```sh
python src/cli.py
```

To use the web service
```sh
streamlit run src/web.py
```
Voila, there you go, you have it running on your device

You can read more about the <a href="https://github.com/ajalamarvellous/bibleverse">project</a> here and how to contribute if you're interested in.

{% raw %}
```html
<div class="row justify-content-sm-center">
    <div class="col-sm-8 mt-3 mt-md-0">
        {% include figure.html path="assets/img/6.jpg" title="example image" class="img-fluid rounded z-depth-1" %}
    </div>
    <div class="col-sm-4 mt-3 mt-md-0">
        {% include figure.html path="assets/img/11.jpg" title="example image" class="img-fluid rounded z-depth-1" %}
    </div>
</div>
```
{% endraw %}
