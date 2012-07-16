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
    <link rel="stylesheet" type="text/css" href="/ui/stripes.css" />
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

        <h2>Testplans</h2>
        <div id="testplans" on-request="true" load="/testplans?format=xml&amp;root=testplans" />

        <h2>Testsuites</h2>
        <div id="testsuites" on-request="true" load="/testsuites?format=xml&amp;root=testsuites" />

        <h2>Profiles</h2>
        <div id="profiles" on-request="true" load="/profiles?format=xml&amp;root=profiles" />

        <h2>Hosts</h2>
        <div id="hosts" on-request="true" load="/hosts?format=xml&amp;root=hosts" />

        <script type="text/javascript" src="/ui/index.js"></script>
    </div>
    <div id="footer">
        <a href="http://gitorious.org/ovirt/igord">More about igor</a>
    </div>
  </body>
  </html>
</xsl:template>

<xsl:template match="/jobs">
<table>
    <thead>
        <tr>
            <th width="10%">Job</th>
            <th width="10%"/>
            <th width="75%"/>
        </tr>
    </thead>
    <tbody>
    <xsl:for-each select="all/*">
        <xsl:sort select="created_at" order="descending"/>
        <xsl:call-template name="job"/>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template name="job">
<tr>
    <td rowspan="5"><xsl:value-of select ="./id"/></td>
</tr>
<tr>
    <th>State:</th>
    <td>
        <xsl:value-of select ="./state"/>
        <a style="float: right">
            <xsl:attribute name="href">
                <xsl:text>/job/report/</xsl:text><xsl:value-of select ="./id"/>
            </xsl:attribute>
            Report
        </a>
    </td>
</tr>
<tr>
    <th>Host:</th>
    <td>
        <xsl:attribute name="title">
            <xsl:value-of select ="./host"/>
        </xsl:attribute>
        <xsl:value-of select ="./host"/>
    </td>
</tr>
<tr>
    <th>Profile:</th>
    <td>
        <xsl:attribute name="title">
            <xsl:value-of select ="./profile"/>
        </xsl:attribute>
        <xsl:value-of select ="./profile"/>
    </td>
</tr>
<tr>
    <th>Testsuite:</th>
    <td><xsl:value-of select ="./testsuite/name"/></td>
</tr>
</xsl:template>

<xsl:template match="/testplans">
<table>
    <thead>
    <tr>
    <th>Testplans</th>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
    <tr><td>
        <a href="javascript:void(0)" onclick="$(this).closest('td').find('div').first().slideToggle()">
            <xsl:value-of select ="./name"/>
        </a>
        <a style="float: right">
            <xsl:attribute name="href">
                <xsl:text>/testplans/</xsl:text><xsl:value-of select ="./name"/>/report
            </xsl:attribute>
            Report
        </a>
        <span class="description">
            - <xsl:value-of select ="./description"/>
        </span>
        <div style="display: none" class="small-margin">
            <table>
            <xsl:apply-templates select="job_layouts" />
            </table>
        </div>
    </td></tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template match="job_layouts">
    <tr>
        <td><xsl:value-of select ="./profile"/></td>
        <td><xsl:value-of select ="./testsuite"/></td>
        <td><xsl:value-of select ="./additional_kargs"/></td>
        <td><xsl:value-of select ="./host"/></td>
    </tr>
</xsl:template>

<xsl:template match="/testsuites">
<table>
    <thead>
    <tr>
    <th>Testsuites</th>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
    <tr><td>
        <xsl:attribute name="title">
            <xsl:value-of select ="./origin/name"/>
        </xsl:attribute>
        <a href="javascript:void(0)" onclick="$(this).closest('td').find('div').first().slideToggle()">
            <xsl:value-of select ="./name"/>
        </a>
        <span class="description">
            - <xsl:value-of select ="./description"/>
        </span>
        <!--a><xsl:attribute name="href">
/testsuites/<xsl:value-of select ="./name"/>/download/<xsl:value-of select ="./name"/>.tar
            </xsl:attribute>Download</a-->
        <div style="display: none" class="small-margin">
            <xsl:apply-templates select="testsets" />
        </div>
    </td></tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>

<xsl:template match="testsets">
    <table>
    <tr><td>
        <a href="javascript:void(0)" onclick="$(this).closest('td').find('div').first().slideToggle()">
            <xsl:value-of select ="./name"/>
        </a>
        <div style="display: none">
        <table>
        <xsl:apply-templates select="libs" />
        </table>
        <table>
        <xsl:apply-templates select="testcases" />
        </table>
        </div>
    </td></tr>
    </table>
</xsl:template>

<xsl:template match="libs">
    <xsl:for-each select="*">
    <!--tr>
        <td>
            lib: <i><xsl:value-of select ="name()"/></i>
        </td>
    </tr-->
    </xsl:for-each>
</xsl:template>

<xsl:template match="testcases">
    <tr>
        <td>
            <xsl:value-of select ="./name"/>
        </td>
        <td>
            <a>
                <xsl:attribute name="href">
/testcases
/<xsl:value-of select ="../../name"/>
/<xsl:value-of select ="../name"/>
/<xsl:value-of select ="./name"/>
/source
                </xsl:attribute>
                Source
            </a>
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
    <th>Name</th>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
        <tr>
            <td>
                <xsl:attribute name="title">
                    <xsl:value-of select ="./origin/name"/>
                </xsl:attribute>
                <xsl:value-of select ="./name"/>
            </td>
        </tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>


<xsl:template match="/hosts">
<table>
    <thead>
    <tr>
    <th>Name</th>
    </tr>
    </thead>
    <tbody>
    <xsl:for-each select="./*">
        <tr>
            <td>
                <xsl:attribute name="title">
                    <xsl:value-of select ="./origin/name"/>
                </xsl:attribute>
                <xsl:value-of select ="./name"/>
            </td>
        </tr>
    </xsl:for-each>
    </tbody>
</table>
</xsl:template>


</xsl:stylesheet> 
