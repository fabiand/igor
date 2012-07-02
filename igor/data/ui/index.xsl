<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
  xmlns:fn="http://www.w3.org/2005/xpath-functions">
<!-- vim: sw=2 -->

<xsl:template match="/index">
  <html>
  <head>
    <title>Igor</title>
    <!--link rel="icon" href="/igor.png" type="image/png"/-->
    <script src="http://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
    <script src="https://ajax.googleapis.com/ajax/libs/jqueryui/1.8.18/jquery-ui.min.js"></script>
    <link href='http://fonts.googleapis.com/css?family=Basic' rel='stylesheet' type='text/css'/>
    <link rel="stylesheet" type="text/css" href="/ui/default.css" />
  </head>
  <body>
    <div id="header">
        <h1>Igor</h1>
    </div>
    <div id="content">
        <ul id="toc">
            <li>toc:</li>
        </ul>
        <h2>Jobs</h2>
        <div id="jobs" load="/jobs?format=xml&amp;root=jobs" />

        <h2>Testsuites</h2>
        <div id="testsuites" load="/testsuites?format=xml&amp;root=testsuites" />

        <h2>Profiles</h2>
        <div id="profiles" load="/profiles?format=xml&amp;root=profiles" />

        <script type="text/javascript" src="/ui/index.js"></script>
    </div>
  </body>
  </html>
</xsl:template>

<xsl:template match="/jobs">
<table>
    <thead>
    <tr>
    <td>Job</td>
    <td>Host</td>
    <td>Profile</td>
    <td>Testsuite</td>
    <td/>
    </tr>
    </thead>
    <tbody>

    <xsl:for-each select="/all">
        <tr>
            <td><xsl:value-of select ="./id"/></td>
            <td><xsl:value-of select ="./host"/></td>
            <td><xsl:value-of select ="./profile"/></td>
            <td><xsl:value-of select ="./testsuite/name"/></td>
        </tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template match="/testsuites">
<table>
    <thead>
    <tr>
    <td>Testsuites</td>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
    <tr><td>
        <a onclick="$(this).closest('tr').next().find('div').first().slideToggle()">
            <xsl:value-of select ="./name"/>
        </a>
    </td></tr>
    <tr><td><div style="display: none">
        <xsl:apply-templates select="testsets" />
    </div></td></tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template match="testsets">
    <table>
    <tr><td>
        <a onclick="$(this).closest('tr').next().find('div').first().slideToggle()">
            <xsl:value-of select ="./name"/>
        </a>
    </td></tr>
    <tr><td><div style="display: none">
    <table>
    <xsl:apply-templates select="testcases" />
    </table>
    </div></td></tr>
    </table>
</xsl:template>

<xsl:template match="testcases">
    <tr>
        <td>
            <xsl:value-of select ="./name"/>
        </td>
        <td>
            <xsl:value-of select ="./timeout"/>
        </td>
    </tr>
</xsl:template>


<xsl:template match="/profiles">
<table>
    <thead>
    <tr>
    <td>Name</td>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
        <tr>
            <td>
                <xsl:value-of select ="./name"/>
            </td>
        </tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>


</xsl:stylesheet> 
