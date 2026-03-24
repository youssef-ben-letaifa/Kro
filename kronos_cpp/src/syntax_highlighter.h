// Kronos IDE — Native Python syntax highlighter
#pragma once

#include <QRegularExpression>
#include <QSyntaxHighlighter>
#include <QTextCharFormat>
#include <QVector>

#include <cstdint>

class PythonHighlighter final : public QSyntaxHighlighter {
public:
    explicit PythonHighlighter(std::uintptr_t documentPtr);

protected:
    void highlightBlock(const QString& text) override;

private:
    struct Rule {
        QRegularExpression pattern;
        QTextCharFormat format;
    };

    QVector<Rule> rules_;
    QTextCharFormat keywordFormat_;
    QTextCharFormat builtinFormat_;
    QTextCharFormat stringFormat_;
    QTextCharFormat commentFormat_;
    QTextCharFormat numberFormat_;
    QTextCharFormat operatorFormat_;
    QTextCharFormat decoratorFormat_;

    void initFormats();
    void initRules();
};
