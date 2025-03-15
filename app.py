from flask import Flask, render_template, request, jsonify, redirect, url_for
import yaml
import json
import os
from datetime import datetime, timedelta
from arxiv_fetcher import fetch_papers, load_config

app = Flask(__name__)

# 默认配置文件路径
DEFAULT_CONFIG_FILE = 'config.yaml'

# arXiv类别列表
ARXIV_CATEGORIES = [
    'cs.AI', 'cs.CL', 'cs.CV', 'cs.DL', 'cs.IR', 'cs.LG', 'cs.MA', 'cs.NE',
    'stat.ML', 'cs.HC', 'cs.SI', 'cs.CY', 'cs.RO'
]

def load_default_config():
    """加载默认配置"""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        with open(DEFAULT_CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f)
    return {
        "keywords": {
            "Large Language Models": {
                "filters": ["LLM", "Large Language Model", "GPT", 
                          "Foundation Model", "Generative AI", "Language Model"]
            },
            "NLP": {
                "filters": ["Natural Language Processing", "NLP", "Language Understanding", 
                          "Language Generation", "Text Analysis", "Semantic Understanding"]
            }
        }
    }

@app.route('/')
def index():
    """主页"""
    config = load_default_config()
    return render_template('index.html', 
                          categories=ARXIV_CATEGORIES,
                          keywords=config['keywords'],
                          today=datetime.now().strftime('%Y-%m-%d'),
                          week_ago=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))

@app.route('/search', methods=['POST'])
def search():
    """处理搜索请求"""
    try:
        # 获取表单数据
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        max_results = int(request.form.get('max_results', 50))
        categories = request.form.getlist('categories')
        
        # 处理关键词
        keywords = {}
        for key in request.form:
            if key.startswith('topic_'):
                topic_id = key.replace('topic_', '')
                topic_name = request.form[key]
                if topic_name and f'filters_{topic_id}' in request.form:
                    filters_str = request.form[f'filters_{topic_id}']
                    filters = [f.strip() for f in filters_str.split(',') if f.strip()]
                    if filters:
                        keywords[topic_name] = filters
        
        # 获取论文
        results = fetch_papers(
            keywords_dict=keywords,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            categories=categories if categories else None
        )
        
        # 渲染结果页面
        return render_template('results.html', 
                              results=results,
                              date_from=date_from,
                              date_to=date_to,
                              categories=categories,
                              max_results=max_results)
    
    except Exception as e:
        return render_template('index.html', 
                              error=str(e),
                              categories=ARXIV_CATEGORIES,
                              keywords=load_default_config()['keywords'],
                              today=datetime.now().strftime('%Y-%m-%d'),
                              week_ago=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))

@app.route('/save_config', methods=['POST'])
def save_config():
    """保存配置到文件"""
    try:
        # 处理关键词
        keywords = {}
        for key in request.form:
            if key.startswith('topic_'):
                topic_id = key.replace('topic_', '')
                topic_name = request.form[key]
                if topic_name and f'filters_{topic_id}' in request.form:
                    filters_str = request.form[f'filters_{topic_id}']
                    filters = [f.strip() for f in filters_str.split(',') if f.strip()]
                    if filters:
                        keywords[topic_name] = {"filters": filters}
        
        # 保存到配置文件
        config = {"keywords": keywords}
        with open(DEFAULT_CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return jsonify({"status": "success", "message": "Configuration saved successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)