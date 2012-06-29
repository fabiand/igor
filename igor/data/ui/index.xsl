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
        <ul id="toc">
            <li>toc:</li>
        </ul>
    </div>
    <div id="content">
        <h2>Jobs</h2>
        <div id="testsuites" load="/jobs?format=xml&amp;root=jobs" />

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
    <td>Runtime</td>
    <td>Testcase</td>
    <td/>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="/all">
        <tr>
            <td><xsl:value-of select ="./id"/></td>
            <td><xsl:value-of select ="./testsuite/name"/></td>
            <td><xsl:value-of select ="./profile"/></td>
            <td><xsl:value-of select ="./host"/></td>
            <td>Abort</td>
        </tr>
        <xsl:apply-templates select="testsets" />
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template match="/testsuites">
<table>
    <thead>
    <tr>
    <td>Testsuite</td>
    <td>Testset</td>
    <td>Testcase</td>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
        <tr>
            <td colspan="3">
                <xsl:value-of select ="./name"/>
            </td>
        </tr>
        <xsl:apply-templates select="testsets" />
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template match="testsets">
    <tr>
        <td/>
        <td colspan="2">
           <xsl:value-of select ="./name"/>
        </td>
    </tr>
    <xsl:apply-templates select="testcases" />
</xsl:template>

<xsl:template match="testcases">
    <tr>
        <td colspan="2" />
        <td>
            <xsl:value-of select ="./name"/> 
            (<xsl:value-of select ="./timeout"/>)
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
