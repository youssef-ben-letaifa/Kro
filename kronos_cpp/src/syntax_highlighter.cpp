// Kronos IDE — Native Python syntax highlighter

#include "syntax_highlighter.h"

#include <QColor>
#include <QFont>
#include <QTextDocument>

#include <stdexcept>

namespace {
constexpr const char* kKeywordColor = "#58A6FF";
constexpr const char* kBuiltinColor = "#79B8FF";
constexpr const char* kStringColor = "#3FB950";
constexpr const char* kCommentColor = "#8B949E";
constexpr const char* kNumberColor = "#D29922";
constexpr const char* kOperatorColor = "#F85149";
constexpr const char* kDecoratorColor = "#58A6FF";
}  // namespace

PythonHighlighter::PythonHighlighter(std::uintptr_t documentPtr)
    : QSyntaxHighlighter(reinterpret_cast<QTextDocument*>(documentPtr)) {
    auto* document = reinterpret_cast<QTextDocument*>(documentPtr);
    if (document == nullptr) {
        throw std::runtime_error("PythonHighlighter requires a valid QTextDocument pointer.");
    }
    initFormats();
    initRules();
}

void PythonHighlighter::initFormats() {
    keywordFormat_.setForeground(QColor(kKeywordColor));
    keywordFormat_.setFontWeight(QFont::Bold);

    builtinFormat_.setForeground(QColor(kBuiltinColor));

    stringFormat_.setForeground(QColor(kStringColor));

    commentFormat_.setForeground(QColor(kCommentColor));
    commentFormat_.setFontItalic(true);

    numberFormat_.setForeground(QColor(kNumberColor));

    operatorFormat_.setForeground(QColor(kOperatorColor));

    decoratorFormat_.setForeground(QColor(kDecoratorColor));
    decoratorFormat_.setFontWeight(QFont::Bold);
}

void PythonHighlighter::initRules() {
    const QStringList keywords = {
        "and", "as", "assert", "break", "class", "continue", "def", "del",
        "elif", "else", "except", "False", "finally", "for", "from", "global",
        "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or",
        "pass", "raise", "return", "True", "try", "while", "with", "yield", "match", "case"
    };
    for (const QString& keyword : keywords) {
        rules_.append({QRegularExpression(QString("\\b%1\\b").arg(keyword)), keywordFormat_});
    }

    const QStringList builtins = {
        "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len",
        "list", "map", "max", "min", "print", "range", "set", "str", "sum", "tuple", "zip"
    };
    for (const QString& builtin : builtins) {
        rules_.append({QRegularExpression(QString("\\b%1\\b").arg(builtin)), builtinFormat_});
    }

    rules_.append({QRegularExpression(R"(\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)"), numberFormat_});
    rules_.append({QRegularExpression(R"([\+\-\*\/\%\=\!\<\>\&\|\^\~\:]+)"), operatorFormat_});
    rules_.append({QRegularExpression(R"(^\s*\@[A-Za-z_][A-Za-z0-9_\.]*)"), decoratorFormat_});
    rules_.append({QRegularExpression(R"(#.*$)"), commentFormat_});
    rules_.append({QRegularExpression(R"("""[^"\\]*(?:\\.[^"\\]*)*""")"), stringFormat_});
    rules_.append({QRegularExpression(R"('''[^'\\]*(?:\\.[^'\\]*)*''')"), stringFormat_});
    rules_.append({QRegularExpression(R"("[^"\\]*(?:\\.[^"\\]*)*")"), stringFormat_});
    rules_.append({QRegularExpression(R"('[^'\\]*(?:\\.[^'\\]*)*')"), stringFormat_});
}

void PythonHighlighter::highlightBlock(const QString& text) {
    for (const Rule& rule : rules_) {
        auto it = rule.pattern.globalMatch(text);
        while (it.hasNext()) {
            const auto match = it.next();
            if (match.hasMatch()) {
                setFormat(match.capturedStart(), match.capturedLength(), rule.format);
            }
        }
    }
}
